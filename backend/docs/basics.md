# SQLAlchemy、Alembic、Pydantic、APScheduler 快速入门

本文只覆盖在本项目开始开发时需要掌握的知识。项目当前使用 **SQLAlchemy 2.0、Alembic 1.18、Pydantic 2、APScheduler 3**；下面的写法以这些版本为准。FastAPI 路由和依赖注入先读 [FastAPI 入门](tutorial.md)，整体目录关系见 [技术架构](../../docs/arch.md)。

| 工具 | 解决什么问题 | 本项目主要位置 |
| --- | --- | --- |
| SQLAlchemy | 用 Python 模型读写关系数据库 | [数据库连接](../app/core/database.py)、[模型基类](../app/core/base_model.py)、[通用 CRUD](../app/core/base_crud.py) |
| Alembic | 记录并执行数据库表结构变更 | [配置](../alembic.ini)、[迁移环境](../app/alembic/env.py)、[迁移目录](../app/alembic/versions/) |
| Pydantic | 校验输入、定义输出、读取配置 | [公共 Schema](../app/core/base_schema.py)、[配置](../app/config/setting.py) |
| APScheduler | 按时间执行任务 | [调度器](../app/core/ap_scheduler.py)、[定时任务模块](../app/modules/task/) |

## 1. SQLAlchemy：模型、查询和事务

**Model 是数据库表的 Python 定义。**一个类通常对应一张表；类属性对应列。SQLAlchemy 2 的常用声明是 `Mapped[类型]` 加 `mapped_column()`：

```python
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin, UserMixin

class NoteModel(ModelMixin, UserMixin):
    __tablename__ = "user_note"

    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

这里 `Mapped[str | None]` 表示 Python 属性可以是字符串或 `None`；数据库是否允许空值仍应明确看 `nullable`。本项目的 `ModelMixin` 提供 ID、时间和软删除字段，`UserMixin` 提供创建人等审计字段。实际业务模型可参考 [DemoModel](../app/plugin/module_example/demo/model.py)。

**Engine 管连接池，Session 管一次工作中的数据库操作。**本项目使用异步 `AsyncEngine` 与 `AsyncSession`。接口通过 `db_getter()` 获取 Session；同一请求的操作在一个事务中，正常结束提交，异常回滚。业务 CRUD 通常只 `flush()`，由请求事务负责最终提交。[项目实现](../app/core/dependencies.py)

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def list_notes(db: AsyncSession) -> list[NoteModel]:
    result = await db.execute(
        select(NoteModel).where(NoteModel.is_deleted.is_(False))
    )
    return list(result.scalars().all())

async def create_note(db: AsyncSession, title: str) -> NoteModel:
    note = NoteModel(title=title)
    db.add(note)
    await db.flush()       # SQL 发给数据库，通常可取得自增 ID
    return note            # 此处尚不代表事务已提交
```

常用操作：`select(Model).where(...)` 构建查询；`await db.execute(...)` 执行；`result.scalars().all()` 取模型列表，`scalar_one_or_none()` 取零或一条；`db.add(obj)` 添加对象；修改已加载对象的属性后 `flush()`。关系字段可能触发额外查询，列表页要按需预加载，避免逐行查关联数据。

**入门要记住：**`flush` 把待执行 SQL 发送到当前事务，`commit` 才提交事务；一个 `AsyncSession` 不应在多个并发任务中共享。数据库表已存在时，改 Model 本身不会修改表结构，需要 Alembic。[SQLAlchemy ORM 快速入门](https://docs.sqlalchemy.org/en/20/orm/quickstart.html) · [异步 ORM](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

## 2. Alembic：让数据库结构跟上 Model

Alembic 的迁移文件记录“数据库从旧结构怎样变成新结构”。文件包含 `upgrade()`（向前更新）和 `downgrade()`（回退）；数据库的 `alembic_version` 表保存当前版本号。它管理**表结构**，已有数据的搬迁或回填往往需要手写迁移逻辑。

修改字段或新增表时，按下面的顺序操作：

1. 修改或新增 `model.py`；本项目会扫描模型文件，供建表和自动比较使用。
2. 在 `backend/` 目录生成迁移：

   ```bash
   uv run main.py revision --env=dev -m "新增笔记表"
   ```

3. 打开 `app/alembic/versions/` 中的新文件，检查 `upgrade()` 和 `downgrade()`。重点看意外的 `drop_table`、`drop_column`、字段重命名和非空字段的旧数据。
4. 确认后执行：

   ```bash
   uv run main.py upgrade --env=dev
   ```

5. 将 Model 和需要保留的迁移文件一起纳入版本管理，再部署到其他环境。

一个新增字段迁移大致是：

```python
def upgrade() -> None:
    op.add_column(
        "user_note",
        sa.Column("summary", sa.String(200), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("user_note", "summary")
```

本项目的 [`env.py`](../app/alembic/env.py) 将 SQLAlchemy 模型元数据交给 Alembic 比较，并使用异步数据库连接。应用启动时，[初始化脚本](../app/scripts/initialize.py) 对空库执行 `create_all()`；已有库执行 `upgrade head`。开发环境还会尝试自动生成并应用迁移；检测到自动生成的删除操作时会拦截，要求人工处理。因此开发时应及时查看迁移结果，不能只依赖启动日志。

当前仓库的 `versions/` 只有 `__init__.py`，没有现成的迁移历史。`stamp head` 只是标记版本，不执行 DDL。自动生成也不能可靠识别“重命名”：它可能生成“删除旧字段 + 新增字段”，造成数据丢失，必须人工改成重命名操作。[Alembic 自动生成](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) · [官方教程](https://alembic.sqlalchemy.org/en/latest/tutorial.html)

## 3. Pydantic：定义数据边界

Pydantic 的 `BaseModel` 用于把外部数据校验、转换为有明确字段的对象。FastAPI 用它描述请求体和响应；它**不是数据库表模型**。通常为同一业务分别定义创建、更新和输出 Schema。

```python
from pydantic import BaseModel, ConfigDict, Field

class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str | None = None

class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None

class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str | None
```

使用时：

```python
incoming = NoteCreate.model_validate({"title": "学习 FastAPI"})
data_for_orm = incoming.model_dump()

patch = NoteUpdate.model_validate({"title": "新标题"})
changes = patch.model_dump(exclude_unset=True)  # 只取调用方实际传入的字段

output = NoteOut.model_validate(note_model)     # 从 ORM 对象属性生成输出
redis_json_data = output.model_dump(mode="json") # 日期等转换成 JSON 兼容值
```

三点最常用：无默认值是必填；`str | None` 允许空值，`= None` 才表示可省略；`Field()` 用于长度、范围等约束。更新接口使用 `exclude_unset=True` 避免把未提交的字段覆盖掉。业务中要区分“未提交”和“明确传入 `null`”时，不要再加 `exclude_none=True`。

本项目还用 `BaseSettings` 从环境变量和 `.env.dev/.env.prod` 读取配置，集中定义在 [setting.py](../app/config/setting.py)。业务 Schema 示例见 [demo/schema.py](../app/plugin/module_example/demo/schema.py)。[Pydantic 模型](https://docs.pydantic.dev/latest/concepts/models/) · [字段约束](https://docs.pydantic.dev/latest/concepts/fields/) · [Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

## 4. APScheduler：按时间运行任务

APScheduler 3 的核心概念只有四个：**Scheduler** 管理任务；**Trigger** 决定何时运行；**JobStore** 保存任务定义；**Executor** 执行任务。常用触发器：

| 触发器 | 用途 | 例子 |
| --- | --- | --- |
| `DateTrigger` | 在指定时刻运行一次 | 明天 9 点发送提醒 |
| `IntervalTrigger` | 固定间隔重复运行 | 每 10 分钟检查一次 |
| `CronTrigger` | 按日历规则重复运行 | 每天 2 点清理 |

以下是**独立示例**，展示 APScheduler 3 的基本写法；在本项目中应使用现有调度服务注册任务，避免另外启动一个调度器：

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def refresh_report() -> None:
    print("更新报表")

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
scheduler.add_job(
    refresh_report,
    trigger="interval",
    minutes=10,
    id="refresh_report",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
scheduler.start()
# 应用关闭时调用 scheduler.shutdown()
```

`max_instances=1` 防止同一任务在上一次未结束时并发重叠；`coalesce=True` 将积压的多个计划执行时间合并。任务错过运行时刻的容忍时间由 `misfire_grace_time` 控制。若任务保存在持久化 JobStore，重启后会重新加载定义；任务函数应能被模块路径导入，避免用 lambda 或局部函数。

本项目使用 [`AsyncIOScheduler`](../app/core/ap_scheduler.py)，默认任务存储在 Redis，还配置了 SQLAlchemy 和内存 JobStore；应用的 [`lifespan`](../app/__init__.py) 负责启动和关闭。多个 Uvicorn Worker 共用 JobStore 时，项目通过 Redis 锁选出一个实际运行调度器的进程，避免每个 Worker 都执行同一任务。定时任务应考虑重复执行时的幂等性；调度器和数据库提交不能天然组成一个事务。[APScheduler 3 用户指南](https://apscheduler.readthedocs.io/en/3.x/userguide.html)

## 5. 新增业务功能时怎样把四者串起来

```text
Pydantic Schema 校验 HTTP 输入
    ↓
Service 编排业务规则
    ↓
SQLAlchemy Model / Session 读写数据
    ↓
Alembic 将 Model 的结构变化应用到已有数据库
    ↓
如需定时处理，再由 APScheduler 调用独立的任务函数
```

最简单的开发顺序：先写 `model.py` 和 `schema.py`，再写 CRUD/Service/Controller；需要改已有数据库时生成并检查迁移；只有确实存在定时需求时才加入任务。四者各管一件事：**表结构与读写、结构版本、输入输出校验、时间调度**。
