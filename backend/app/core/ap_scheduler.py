import asyncio
import inspect
import re
from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.job import Job
from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import false, select, update
from sqlalchemy.orm import Session

from app.config.setting import settings
from app.core.database import async_db_session, engine
from app.core.exceptions import CustomException
from app.core.logger import logger

# 常见执行失败模式的中文结论（匹配原始异常文本；任意第三方异常无法机翻，保留原文供诊断）
_JOB_ERROR_HINTS: list[tuple[str, str]] = [
    ("maximum number of running instances", "任务已达最大并发实例数，本次执行被跳过（可调大节点的 max_instances）"),
    ("was missed by", "任务错过计划执行时间（misfire，通常因进程繁忙或重启空窗）"),
    ("Unauthorized", "上游认证失败（HTTP 401），请检查访问令牌"),
    ("rate limit", "触发上游限流（HTTP 429），请稍后重试"),
    ("Connection", "网络连接异常，请检查目标地址与网络"),
    ("Timeout", "请求超时"),
]


def _humanize_job_error(detail: Any) -> str:
    """把执行异常转成"中文结论｜原始信息"回显；未命中已知模式时原样返回。"""
    text = str(detail)[:4000]
    for pattern, hint in _JOB_ERROR_HINTS:
        if pattern in text:
            return f"{hint}｜原始信息: {text}"[:4000]
    return text

# 数据库只保存任务定义与执行日志，运行计划统一保存在当前进程内存中。
scheduler = AsyncIOScheduler(
    jobstores={"default": MemoryJobStore()},
    executors={"default": ThreadPoolExecutor(max_workers=10)},
    job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60},
    timezone="Asia/Shanghai",
)


class SchedulerUtil:
    """单机调度：应用生命周期启停，任务配置只由任务管理维护。"""

    BUILTIN_PREFIX = "builtin:"
    BUILTIN_HANDLERS_MODULE = "app.modules.task.node.handlers"
    _BUILTIN_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)?$")
    _builtin_handlers: dict[str, Callable[..., Any]] = {}

    @classmethod
    async def init_scheduler(cls) -> None:
        """先从数据库加载任务，再启动调度；停机期间的计划不补执行。"""
        from app.modules.task.job.model import JobModel
        from app.modules.task.node.model import NodeModel
        from app.modules.task.node.service import register_node_job

        async with async_db_session() as session, session.begin():
            # 单机上次异常退出时留下的执行中日志，标记为中断。
            await session.execute(
                update(JobModel).where(JobModel.status == 1, JobModel.is_deleted == false()).values(
                    status=5, finished_time=datetime.now(UTC), error="服务重启，上次执行已中断",
                )
            )
            nodes = (await session.execute(select(NodeModel).where(
                NodeModel.is_deleted == false(), NodeModel.status == 0,
            ))).scalars().all()
            for node in nodes:
                try:
                    register_node_job(node)
                except (ValueError, CustomException) as exc:
                    logger.warning("任务 {} 未注册: {}", node.id, exc)
        scheduler.start()
        logger.info("✅ 本机定时任务调度器已启动，已加载 {} 个任务", len(cls.get_jobs()))

    @classmethod
    async def shutdown(cls, wait: bool = False) -> None:
        """仅在应用退出时关闭调度器。"""
        if scheduler.running:
            scheduler.shutdown(wait=wait)
            await asyncio.sleep(0)

    @classmethod
    def pause(cls) -> None:
        scheduler.pause()

    @classmethod
    def resume(cls) -> None:
        scheduler.resume()

    @classmethod
    def is_running(cls) -> bool:
        return scheduler.state == 1

    @classmethod
    def is_scheduler_ready(cls) -> bool:
        return scheduler.running

    @classmethod
    def get_scheduler_state(cls) -> int:
        return scheduler.state

    @classmethod
    def get_job(cls, job_id: str | int) -> Job | None:
        return scheduler.get_job(str(job_id))

    @classmethod
    def get_jobs(cls) -> list[Job]:
        # 监控只展示正式计划；手动执行的结果统一到任务执行日志查看。
        return [job for job in scheduler.get_jobs() if job.id.isdigit()]

    @classmethod
    def remove_job(cls, job_id: str | int) -> None:
        try:
            scheduler.remove_job(str(job_id))
        except JobLookupError:
            pass

    @classmethod
    def add_job(cls, definition: dict[str, Any], trigger: Any, *, job_id: str | None = None) -> Job:
        """定时与手动任务共用执行入口，传入独立的任务快照。"""
        manual = job_id is not None
        return scheduler.add_job(
            cls.execute_task,
            trigger=trigger,
            id=job_id or definition["id"],
            name=definition["name"],
            args=[definition, "manual" if manual else definition["trigger"]],
            replace_existing=not manual,
            coalesce=definition["coalesce"],
            max_instances=definition["max_instances"],
        )

    @classmethod
    def execute_task(cls, definition: dict[str, Any], trigger_type: str) -> Any:
        """在线程池执行任务，直接携带元数据记录开始与完成，不反查已移除的 Job。"""
        from app.modules.task.job.model import JobModel

        started = datetime.now(UTC)
        timer = perf_counter()
        record = {
            "job_id": definition["id"], "job_name": definition["name"],
            "trigger_type": trigger_type, "started_time": started, "status": 1,
        }
        record_id = None
        try:
            with Session(engine) as session:
                log = JobModel(**record)
                session.add(log)
                session.commit()
                record_id = log.id
        except Exception:
            logger.exception("任务 {} 开始日志写入失败", definition["id"])

        status, result, error = 2, None, None
        try:
            result = cls._task_wrapper(
                definition["id"], definition["func"], *definition["args"], **definition["kwargs"],
            )
            if inspect.isawaitable(result):
                async def await_result():
                    return await result
                result = asyncio.run(await_result())
            return result
        except Exception as exc:
            status, error = 3, _humanize_job_error(exc)
            raise
        finally:
            record.update(
                status=status, result=str(result)[:4000] if status == 2 and result is not None else None,
                error=error, finished_time=datetime.now(UTC),
                duration_ms=round((perf_counter() - timer) * 1000, 3),
            )
            try:
                with Session(engine) as session:
                    if record_id is None:
                        session.add(JobModel(**record))
                    else:
                        session.execute(update(JobModel).where(JobModel.id == record_id).values(**record))
                    session.commit()
            except Exception:
                logger.exception("任务 {} 完成日志写入失败", definition["id"])

    @classmethod
    def describe_schedulability(cls, code_block: str | None) -> tuple[bool, str | None]:
        """判断某个 func（代码块 / ``builtin:`` 引用）当前是否可调度。

        单一事实来源：创建/更新守卫、节点列表状态字段、调度器巡检日志都调用它，
        避免各处对 ``SCHEDULER_ALLOW_CODE_EXEC`` 的理解不一致。

        参数:
        - code_block (str | None): 节点的 func 字段。

        返回:
        - tuple[bool, str | None]: (是否可调度, 不可调度原因)。
        """
        raw = (code_block or "").strip()
        if not raw:
            return False, "未配置函数或代码块（节点不会执行）"
        if raw.startswith(cls.BUILTIN_PREFIX):
            try:
                cls.resolve_builtin_handler(raw)
            except ValueError as exc:
                return False, f"内置处理器不可用：{exc}"
            return True, None
        if not settings.SCHEDULER_ALLOW_CODE_EXEC:
            return False, (
                "服务端已禁用代码块执行（SCHEDULER_ALLOW_CODE_EXEC=False）；"
                "请改用内置函数型任务——把 func 改为 builtin:<模块名>[.<函数名>]（不经 exec，不受该开关限制）"
            )
        return True, None

    @classmethod
    def require_schedulable(cls, code_block: str | None) -> None:
        """不可调度时抛出业务异常；可调度时直接返回。

        把「取判定结果 + 抛异常」收敛到一处：``describe_schedulability`` 的 reason 是
        ``str | None``（可调度时为 None），调用点直接 ``CustomException(msg=reason)`` 会
        传入 None 让客户端收到空文案；这里统一兜底，也避免每个调用点各写一份兜底文案。

        参数:
        - code_block (str | None): 节点的 func 字段。

        异常:
        - CustomException: 当前不可调度时抛出（含可操作原因）。
        """
        schedulable, reason = cls.describe_schedulability(code_block)
        if not schedulable:
            raise CustomException(msg=reason or "当前任务不可调度，请检查任务配置")

    @classmethod
    def register_builtin_handler(cls, name: str, handler: Callable[..., Any]) -> None:
        """注册一个内置处理器（供无 exec 的「内置函数型任务」使用）。

        参数:
        - name (str): 名称（``func = "builtin:<name>"`` 时引用）。
        - handler (Callable): 可调用对象。

        返回:
        - None
        """
        cls._builtin_handlers[name] = handler

    @classmethod
    def resolve_builtin_handler(cls, code_block: str | None) -> Callable[..., Any] | None:
        """解析 ``builtin:<name>`` 引用；非内置引用返回 None。

        参数:
        - code_block (str | None): 节点的 func 字段。

        返回:
        - Callable | None: 内置处理器；不是内置引用时返回 None。

        异常:
        - ValueError: 引用形态非法、模块/函数不存在或不是可调用对象时抛出
          （**绝不回退到 exec**，避免"看起来是内置任务、实际被执行成代码块"）。
        """
        raw = (code_block or "").strip()
        if not raw.startswith(cls.BUILTIN_PREFIX):
            return None
        name = raw[len(cls.BUILTIN_PREFIX) :].strip()
        if not cls._BUILTIN_NAME_RE.match(name):
            raise ValueError(f"内置处理器名称非法（仅允许 模块名[.函数名]，实际 {raw!r}）")

        cached = cls._builtin_handlers.get(name)
        if cached is not None:
            return cached

        module_name, _, func_name = name.partition(".")
        func_name = func_name or module_name
        import importlib

        module_path = f"{cls.BUILTIN_HANDLERS_MODULE}.{module_name}"
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            raise ValueError(f"内置处理器模块不存在：{module_path}") from exc
        handler = getattr(module, func_name, None)
        if handler is None or not callable(handler):
            raise ValueError(f"内置处理器不可用（{module_path}.{func_name} 不存在或不可调用）")
        # 安全加固（复核 R1）：只接受「在本模块内定义」或「该模块显式声明」的可调用对象。
        # 否则 handler 模块里任何一条 `from os import system` 之类的导入，都会变成
        # 绕过 SCHEDULER_ALLOW_CODE_EXEC 的无限制执行入口。
        declared = getattr(module, "HANDLERS", None)
        if isinstance(declared, dict):
            if declared.get(func_name) is not handler:
                raise ValueError(f"内置处理器未在该模块的 HANDLERS 中声明：{module_path}.{func_name}")
        elif getattr(handler, "__module__", None) != module.__name__:
            raise ValueError(
                f"内置处理器必须在本模块内定义或经 HANDLERS 声明：{module_path}.{func_name} "
                f"实际来自 {getattr(handler, '__module__', '未知来源')}，已拒绝"
            )
        cls._builtin_handlers[name] = handler
        return handler

    @classmethod
    def _task_wrapper(cls, job_id: str | int, code_block: str | None, *args, **kwargs):
        """任务执行包装器，执行自定义代码块（同步版本，用于 ThreadPoolExecutor）

        两类任务：
        - **内置函数型**（``code_block = "builtin:<模块名>[.<函数名>]"``）：走白名单注册表直接调用，
          **不使用 exec**，因此不受 ``SCHEDULER_ALLOW_CODE_EXEC`` 限制；
        - **代码块型**（其它内容）：``exec`` 等于给所有能创建任务的人服务器代码执行权限，**默认关闭**，
          关闭时执行入口直接失败并把原因写入执行日志（而不是静默跳过）。
        """
        # 内置函数型任务（builtin:<name>）：白名单解析后直接调用，不经过 exec，
        # 因此即使 SCHEDULER_ALLOW_CODE_EXEC=False 也能正常调度
        raw_code = (code_block or "").strip()
        if raw_code.startswith(cls.BUILTIN_PREFIX):
            handler = cls.resolve_builtin_handler(raw_code)
            logger.info(f"任务 {job_id} 以内置处理器执行（不经 exec）: {raw_code}")
            return handler(*args, **kwargs) if handler else None

        if raw_code and not settings.SCHEDULER_ALLOW_CODE_EXEC:
            message = (
                f"任务 {job_id} 含用户提交的代码块，已拒绝执行：服务端默认禁止定时任务执行代码块。"
                f"如确需该能力，请显式设置 SCHEDULER_ALLOW_CODE_EXEC=true（等同授予服务器代码执行权限，请谨慎评估）；"
                f"若只需内置能力，可把 func 改为 builtin:<模块名>[.<函数名>]"
            )
            logger.error(message)
            raise RuntimeError(message)

        import types

        def run_sync_handler():
            if not code_block:
                return None
            module = types.ModuleType(f"node_task_{job_id}")
            module.__dict__["__builtins__"] = __builtins__
            exec(code_block, module.__dict__)
            handler = module.__dict__.get("handler")
            if handler and callable(handler):
                return handler(*args, **kwargs)
            raise ValueError("代码块必须定义 handler(*args, **kwargs) 函数")

        try:
            return run_sync_handler()
        except Exception as e:
            logger.error(f"任务 {job_id} 执行失败: {e!s}")
            raise
