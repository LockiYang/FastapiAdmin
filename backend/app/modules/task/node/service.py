import json
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from apscheduler.job import Job
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from croniter import croniter
from sqlalchemy import event, false, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ap_scheduler import SchedulerUtil
from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.core.logger import logger
from app.core.validator import datetime_validator
from app.utils.common_util import search_to_dict

from .crud import NodeCRUD
from .model import NodeModel
from .schema import (
    NodeCreateSchema,
    NodeOutSchema,
    NodeQueryParam,
    NodeRunResultSchema,
    NodeUpdateSchema,
)


class NodeService:
    """节点管理模块服务层"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def options(self) -> list[NodeOutSchema]:
        obj_list = await NodeCRUD(self.auth, self.db).get_obj_list_crud()
        return [NodeOutSchema.model_validate(obj) for obj in obj_list]

    async def detail(self, id: int) -> NodeOutSchema:
        obj = await NodeCRUD(self.auth, self.db).get_obj_by_id_crud(id=id)
        if not obj:
            raise CustomException(msg="该节点不存在")
        out = NodeOutSchema.model_validate(obj)
        await self._enrich_runtime([out])
        return out

    async def get_list(
        self,
        search: NodeQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> list[NodeOutSchema]:
        obj_list = await NodeCRUD(self.auth, self.db).get_obj_list_crud(search=search_to_dict(search, {}), order_by=order_by)
        out_list = [NodeOutSchema.model_validate(obj) for obj in obj_list]
        await self._enrich_runtime(out_list)
        return out_list

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: NodeQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[NodeOutSchema]:
        offset = (page_no - 1) * page_size
        result = await NodeCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=NodeOutSchema,
        )
        await self._enrich_runtime(list(result.items))
        return result

    async def create(self, data: NodeCreateSchema) -> NodeOutSchema:
        exist_obj = await NodeCRUD(self.auth, self.db).get(name=data.name)
        if exist_obj:
            raise CustomException(msg="创建失败，该节点已存在")

        validate_node_definition(data)
        obj = await NodeCRUD(self.auth, self.db).create_obj_crud(data=data)
        if not obj:
            raise CustomException(msg="创建失败")
        self._sync_after_commit(obj)
        out = NodeOutSchema.model_validate(obj)
        await self._enrich_runtime([out])
        return out

    async def update(self, id: int, data: NodeUpdateSchema) -> NodeOutSchema:
        exist_obj = await NodeCRUD(self.auth, self.db).get_obj_by_id_crud(id=id)
        if not exist_obj:
            raise CustomException(msg="更新失败，该节点不存在")

        validate_node_definition(data)
        # 编辑表单是完整定义，显式写入空值才能取消旧计划或清空参数。
        obj = await NodeCRUD(self.auth, self.db).update(id=id, data=data.model_dump())
        if not obj:
            raise CustomException(msg="更新失败")
        self._sync_after_commit(obj)
        out = NodeOutSchema.model_validate(obj)
        await self._enrich_runtime([out])
        return out

    async def delete(self, ids: list[int]) -> None:
        if not ids:
            raise CustomException(msg="删除失败，删除对象不能为空")
        for mid in ids:
            exist_obj = await NodeCRUD(self.auth, self.db).get_obj_by_id_crud(id=mid)
            if not exist_obj:
                raise CustomException(msg="删除失败，该节点不存在")
        await NodeCRUD(self.auth, self.db).delete_obj_crud(ids=ids)
        for node_id in ids:
            self._after_commit(lambda node_id=node_id: SchedulerUtil.remove_job(node_id))

    async def clear(self) -> None:
        # 清空仅清理已软删除的定义，不修改仍启用任务的运行计划。
        await NodeCRUD(self.auth, self.db).clear_obj_crud()

    async def execute(self, id: int) -> NodeRunResultSchema:
        """唯一手动执行入口；与定时执行共用执行函数及日志。"""
        obj = await NodeCRUD(self.auth, self.db).get_obj_by_id_crud(id=id)
        if not obj:
            raise CustomException(msg="执行失败，该任务不存在")
        definition = task_definition(obj)
        job_id = f"{id}:manual:{uuid4().hex}"
        self._after_commit(lambda: SchedulerUtil.add_job(definition, None, job_id=job_id))
        return NodeRunResultSchema(job_id=job_id, status="queued", trigger="manual")

    async def batch_set_status(self, ids: list[int], status: int) -> None:
        """启停先写入数据库，事务提交后同步运行计划。"""
        if not ids:
            raise CustomException(msg="请选择要操作的数据")
        nodes = []
        for node_id in ids:
            node = await NodeCRUD(self.auth, self.db).get_obj_by_id_crud(id=node_id)
            if not node:
                raise CustomException(msg="任务不存在")
            if status == 0:
                validate_node_definition(node)
            nodes.append(node)
        await NodeCRUD(self.auth, self.db).set(ids=ids, status=status)
        for node in nodes:
            node.status = status
            self._sync_after_commit(node)

    def _after_commit(self, action) -> None:
        # 请求事务失败时不改内存计划；回调使用任务快照，不持有 ORM 会话。
        event.listen(self.db.sync_session, "after_commit", lambda _session: action(), once=True)

    def _sync_after_commit(self, node: NodeModel) -> None:
        plan = prepare_node_job(node)
        node_id = str(node.id)
        def apply():
            if plan is None:
                SchedulerUtil.remove_job(node_id)
            else:
                SchedulerUtil.add_job(*plan)
        self._after_commit(apply)

    # ── 运行时信息补充（下次运行/最近运行，来自调度器与执行日志）──────────
    async def _enrich_runtime(self, items: list[NodeOutSchema]) -> None:
        """补充 next_run_time / last_run_time / last_run_status。

        直接查当前请求 db 会话的执行日志表（job_id = 节点 id，含手动执行记录），
        不受 JobCRUD 数据权限模型影响。
        """
        if not items:
            return
        from ..job.model import JobModel  # 延迟导入：避免模块级相互依赖

        jobs = {job.id: job for job in SchedulerUtil.get_jobs()}
        for item in items:
            node_id = str(item.id) if item.id is not None else ""
            job = jobs.get(node_id)
            if job:
                item.next_run_time = str(job.next_run_time) if getattr(job, "next_run_time", None) else None

            schedulable, reason = SchedulerUtil.describe_schedulability(item.func)
            item.schedulable = schedulable
            item.unschedulable_reason = None if schedulable else reason
            stmt = (
                select(JobModel)
                .where(JobModel.job_id == node_id, JobModel.is_deleted == false())
                .order_by(JobModel.created_time.desc())
                .limit(1)
            )
            row = (await self.db.execute(stmt)).scalars().first()
            if row:
                item.last_run_time = row.created_time.isoformat() if row.created_time else None
                item.last_run_status = row.status


def _build_job_trigger(
    trigger: str | None,
    trigger_args: str | None,
    start_date: str | None,
    end_date: str | None,
) -> Any:
    """依据节点持久化计划构造 APScheduler Trigger，非法参数抛 ValueError。"""
    if trigger == "cron":
        cron_expr = (trigger_args or "").strip()
        fields = cron_expr.split()
        if len(fields) not in (6, 7):
            raise ValueError("无效的 Cron 表达式，格式: 秒 分 时 日 月 周 [年]")
        # Quartz 风格的 ? 仅表示"该位无具体值"，croniter 不支持，先统一规范化为 * 再校验
        parsed = [field if field != "?" else "*" for field in fields]
        try:
            croniter(" ".join(parsed))
        except (KeyError, ValueError):
            raise ValueError(f"Cron表达式不正确: {cron_expr}")
        if len(fields) == 6:
            parsed.append("*")
        second, minute, hour, day, month, day_of_week, year = parsed
        if second == "*" and minute == "*" and hour == "*" and day == "*" and month == "*" and day_of_week in ("*", "?"):
            raise ValueError("Cron表达式不允许每秒执行，请至少指定秒数（如：0 * * * * ? * 表示每分钟执行）")
        return CronTrigger(
            second=second,
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            year=year,
            start_date=start_date,
            end_date=end_date,
            timezone="Asia/Shanghai",
        )
    if trigger == "interval":
        interval_args = (trigger_args or "").strip()
        fields = interval_args.split()
        if len(fields) != 5:
            raise ValueError("无效的 interval 表达式，格式: 秒 分 时 天 周")
        second, minute, hour, day, week = tuple(int(field) if field != "*" else 0 for field in fields)
        if min(second, minute, hour, day, week) < 0 or not any((second, minute, hour, day, week)):
            raise ValueError("执行间隔必须大于零，且各项不能为负数")
        return IntervalTrigger(
            weeks=week,
            days=day,
            hours=hour,
            minutes=minute,
            seconds=second,
            start_date=start_date,
            end_date=end_date,
            timezone="Asia/Shanghai",
        )
    if trigger == "date":
        date_str = (trigger_args or "").strip()
        if not date_str:
            raise ValueError("date触发器缺少执行时间参数")
        try:
            datetime_validator(date_str)
        except Exception:
            raise ValueError("date触发时间必须为 YYYY-MM-DD HH:MM:SS")
        return DateTrigger(run_date=date_str, timezone="Asia/Shanghai")
    raise ValueError(f"不支持的触发方式: {trigger}")


def validate_node_definition(node) -> None:
    """落库前校验函数、参数及完整时间范围。"""
    task_definition(node)
    if node.trigger:
        try:
            _build_job_trigger(node.trigger, node.trigger_args, node.start_date, node.end_date)
        except ValueError as exc:
            raise CustomException(msg=str(exc)) from exc


def task_definition(node) -> dict[str, Any]:
    """生成执行所需的普通数据快照，供定时与手动执行复用。"""
    SchedulerUtil.require_schedulable(node.func)
    try:
        kwargs = json.loads(node.kwargs) if node.kwargs and node.kwargs.strip() else {}
    except json.JSONDecodeError as exc:
        raise CustomException(msg="关键字参数必须为 JSON 对象") from exc
    if not isinstance(kwargs, dict):
        raise CustomException(msg="关键字参数必须为 JSON 对象")
    return {
        "id": str(getattr(node, "id", "")), "name": node.name, "func": node.func,
        "args": [arg.strip() for arg in (node.args or "").split(",") if arg.strip()],
        "kwargs": kwargs, "trigger": node.trigger,
        "coalesce": bool(node.coalesce), "max_instances": node.max_instances or 1,
    }


def prepare_node_job(node: NodeModel) -> tuple[dict[str, Any], Any] | None:
    if node.status != 0 or not node.trigger or not (node.func or "").strip():
        return None
    trigger = _build_job_trigger(node.trigger, node.trigger_args, node.start_date, node.end_date)
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    if isinstance(trigger, DateTrigger) and trigger.run_date <= now:
        return None
    if trigger.get_next_fire_time(None, now) is None:
        return None
    return task_definition(node), trigger


def register_node_job(node: NodeModel) -> Job | None:
    """仅从数据库定义创建内存计划，过期计划不补跑。"""
    plan = prepare_node_job(node)
    if plan is None:
        SchedulerUtil.remove_job(node.id)
        return None
    return SchedulerUtil.add_job(*plan)
