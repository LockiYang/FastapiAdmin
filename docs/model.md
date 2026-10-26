# 数据表与 PRD 模块对应关系

本文按 [PRD](prd.md) 的模块划分，说明数据表承载的功能、关键关联和非关系库存储。整理日期：2026-10-26。

本次根据项目 ORM、初始化代码及本机 Agno 2.5.8 源码静态梳理，未连接开发库或线上库。以下是代码定义与建表逻辑的对应关系，不代表某个数据库当前已存在全部表；实际表清单还取决于数据库类型、初始化、迁移历史和模块运行情况。

## 1. 总览

项目在 `backend/app` 中显式定义了 **29 张 ORM 表**，包括实体表和关联表；不含 Agno、APScheduler、Alembic 等框架管理的表。

| 代码域 | 表数 | 对应 PRD |
| --- | --- | --- |
| `system` | 18 | §3 认证、§4 RBAC、§5 组织、§6 配置与字典、§7 内容与其他 |
| `task` | 2 | §8 定时任务 |
| `storage` | 6 | §9 存储与传输 |
| `generator` | 2 | §11 代码生成 |
| `plugin/module_example` | 1 | §13 示例插件 |
| **合计** | **29** | 同一张表可被多个功能复用，不按页面重复计数 |

`task_storage_*` 虽沿用 `task_` 表名前缀，代码已归属独立 `storage` 模块。`task_cornjob_node`、`task_corn_job` 是当前真实表名，保留其现有拼写。

## 2. 项目 ORM 表逐表对应

### 2.1 认证与 RBAC 权限系统

| 表名 | PRD 模块 | 承载功能与关键关联 | 模型源码 |
| --- | --- | --- | --- |
| `sys_user` | §3 认证；§4.1 用户 | 后台账号、密码、超管身份和账号状态；`dept_id` 关联部门，角色和岗位通过关联表分配；认证会话另存 Redis | [user/model.py](../backend/app/modules/system/user/model.py) |
| `sys_role` | §4.2 角色 | 角色定义、启停和 `data_scope`；连接账号与功能权限 | [role/model.py](../backend/app/modules/system/role/model.py) |
| `sys_menu` | §4.3 权限 | 统一表示目录、菜单、按钮与外链；`permission` 用于鉴权，`parent_id` 构成树，路由字段用于前端页面注册 | [menu/model.py](../backend/app/modules/system/menu/model.py) |
| `sys_user_roles` | §4.1 用户；§4.2 角色 | `user_id` ↔ `role_id`，账号与角色多对多；决定账号采用哪些角色授权 | [user/model.py](../backend/app/modules/system/user/model.py) |
| `sys_role_menus` | §4.2 角色；§4.3 权限 | `role_id` ↔ `menu_id`，角色与权限节点多对多 | [role/model.py](../backend/app/modules/system/role/model.py) |
| `sys_role_depts` | §4.2 角色；§5.1 部门 | 现有角色部门关联表；当前保存授权时清空，不参与三档数据范围，不能据此推断支持自定义部门授权 | [role/model.py](../backend/app/modules/system/role/model.py) |

超管由 `sys_user.is_superuser` 识别，不依赖名为 `SUPER_ADMIN` 的角色。普通管理员的功能权限来自有效角色关联的权限节点；数据范围由角色 `data_scope` 配合部门树决定。

### 2.2 组织管理

| 表名 | PRD 模块 | 承载功能与关键关联 | 模型源码 |
| --- | --- | --- | --- |
| `sys_dept` | §5.1 部门 | `parent_id` 自关联形成部门树；账号通过 `sys_user.dept_id` 归属部门，支持部门及子部门数据范围 | [dept/model.py](../backend/app/modules/system/dept/model.py) |
| `sys_position` | §5.2 岗位 | 岗位定义与启停，作为后台账号职务标记，不直接授予权限 | [position/model.py](../backend/app/modules/system/position/model.py) |
| `sys_user_positions` | §4.1 用户；§5.2 岗位 | `user_id` ↔ `position_id`，账号与岗位多对多 | [user/model.py](../backend/app/modules/system/user/model.py) |

### 2.3 配置与字典

| 表名 | PRD 模块 | 承载功能与关键关联 | 模型源码 |
| --- | --- | --- | --- |
| `sys_dict_type` | §6.1 字典管理 | 字典类型，`dict_type` 是唯一类型编码和读取入口 | [dict/model.py](../backend/app/modules/system/dict/model.py) |
| `sys_dict_data` | §6.1 字典管理 | 字典条目，`dict_type_id` 关联类型，并冗余 `dict_type`；保存标签、值、默认项与启停状态 | [dict/model.py](../backend/app/modules/system/dict/model.py) |
| `sys_param` | §6.2 参数管理 | 系统配置键值；`config_key` 定位配置，`config_value` 承载站点信息、访问限制等，修改后同步 Redis | [params/model.py](../backend/app/modules/system/params/model.py) |

### 2.4 内容与其他

| 表名 | PRD 模块 | 承载功能与关键关联 | 模型源码 |
| --- | --- | --- | --- |
| `sys_login_log` | §7.1 日志管理；§3 认证 | 登录成败、来源与结果记录；用 `username` 保存账号快照，不通过用户审计外键关联账号 | [log/model.py](../backend/app/modules/system/log/model.py) |
| `sys_operation_log` | §7.1 日志管理 | 后台操作请求、响应、结果、来源和耗时审计；操作人同样用用户名快照记录 | [log/model.py](../backend/app/modules/system/log/model.py) |
| `sys_notice` | §7.2 公告管理 | 通知、公告正文与草稿、发布、归档状态；SSE 只推送更新事件，不另建事件表 | [notice/model.py](../backend/app/modules/system/notice/model.py) |
| `sys_ticket` | §7.3 工单管理 | 反馈、指派、回复及状态流转；`created_id` 为提交人，`assigned_id` 为处理人，均关联 `sys_user` | [ticket/model.py](../backend/app/modules/system/ticket/model.py) |
| `sys_ticket_comment` | §7.3 工单管理 | `ticket_id` 关联工单，`created_id` 关联评论人；承载工单讨论 | [ticket/model.py](../backend/app/modules/system/ticket/model.py) |
| `sys_version` | §7.4 版本管理 | 产品版本、发布或回滚状态、要求重新登录标记；与框架的数据库迁移版本表不同 | [versions/model.py](../backend/app/modules/system/versions/model.py) |

### 2.5 定时任务

| 表名 | PRD 模块 | 承载功能与关键关联 | 模型源码 |
| --- | --- | --- | --- |
| `task_cornjob_node` | §8 定时任务 | 可重复执行的节点定义：函数、参数、触发计划、启停和并发策略；是任务恢复时读取的业务配置 | [task/node/model.py](../backend/app/modules/task/node/model.py) |
| `task_corn_job` | §8 定时任务 | 每次执行的状态、结果和错误记录；`job_id` 是调度标识，节点任务的临时执行 ID 会归一到节点 ID，不是数据库外键 | [task/job/model.py](../backend/app/modules/task/job/model.py) |

节点表定义“执行什么、何时执行”，执行日志表记录“某次执行结果”；APScheduler 的运行计划由 jobstore 保存，见第 4 节。

### 2.6 存储与传输

| 表名 | PRD 模块 | 承载功能与关键关联 | 模型源码 |
| --- | --- | --- | --- |
| `task_storage_node` | §9.1 存储源；§9.2 文件浏览 | 存储协议、连接配置、加密凭据、默认标记与启停；供浏览、传输、流程复用 | [storage/node/model.py](../backend/app/modules/storage/node/model.py) |
| `task_storage_transfer` | §9.3 传输任务 | 一次传输的源、任务类型、执行状态、进度与结果 | [transfer/model.py](../backend/app/modules/storage/transfer/model.py) |
| `task_storage_transfer_step` | §9.3 传输任务 | `task_id` 外键关联传输任务；步骤序号、源目标路径、传输方式和步骤进度；源目标存储 ID 为业务引用 | [transfer/model.py](../backend/app/modules/storage/transfer/model.py) |
| `task_storage_workflow` | §9.4 传输流程 | 可复用流程定义与启停，`graph` 仅保存画布布局 | [workflow/model.py](../backend/app/modules/storage/workflow/model.py) |
| `task_storage_workflow_node` | §9.4 传输流程 | `flow_id` 归属流程，`node_key` 标识节点，`source_id` 绑定存储源，`source_path` 为默认路径 | [workflow/model.py](../backend/app/modules/storage/workflow/model.py) |
| `task_storage_workflow_edge` | §9.4 传输流程 | `flow_id` 归属流程；源、目标 `node_key` 形成连线，保存是否执行和传输参数 | [workflow/model.py](../backend/app/modules/storage/workflow/model.py) |

流程执行读取节点和连线，再创建 `task_storage_transfer` 与步骤。当前每条启用连线分别创建任务，传输任务没有独立的 `workflow_id` 外键；不能只依靠表关系将所有任务反查为某次流程执行，也不能把连线直接视为已实现完整依赖调度。

文件浏览的上传、下载、删除等操作直接访问存储源，**没有逐文件的统一附件记录表**。传输任务和步骤记录的是执行过程，不替代文件元数据与业务引用记录。

### 2.7 代码生成与示例插件

| 表名 | PRD 模块 | 承载功能与关键关联 | 模型源码 |
| --- | --- | --- | --- |
| `gen_table` | §11 代码生成 | 表级生成配置；目标表、实体、主子表关系与父菜单选择 | [gencode/model.py](../backend/app/modules/generator/gencode/model.py) |
| `gen_table_column` | §11 代码生成 | `table_id` 外键关联表配置；数据库字段、代码映射和表单、列表、查询配置 | [gencode/model.py](../backend/app/modules/generator/gencode/model.py) |
| `example_demo` | §13 示例插件 | 插件加载与通用 CRUD 的演示记录，不承担产品业务 | [demo/model.py](../backend/app/plugin/module_example/demo/model.py) |

生成器配置表保存的是生成规则；生成新业务代码并建表后产生的业务表，应归入该业务模块，不计为生成器配置表。

## 3. 关键关系与数据范围

| 关系 | 实现方式 | 功能含义 |
| --- | --- | --- |
| 账号 ↔ 角色 ↔ 权限节点 | `sys_user_roles`、`sys_role_menus` 的数据库外键 | 多角色功能授权 |
| 账号 → 部门 → 上级部门 | `sys_user.dept_id`、`sys_dept.parent_id` 外键 | 部门归属和范围展开 |
| 账号 ↔ 岗位 | `sys_user_positions` 的数据库外键 | 职务关联，不参与权限判断 |
| 权限节点 → 父节点 | `sys_menu.parent_id` 外键 | 菜单树与启停、删除联动 |
| 字典条目 → 类型 | `sys_dict_data.dict_type_id` 外键 | 一对多；`dict_type` 同步保存类型编码 |
| 工单 → 处理人；评论 → 工单 | `assigned_id`、`ticket_id` 外键 | 指派与讨论，评论依赖工单 |
| 传输步骤 → 任务 | `task_storage_transfer_step.task_id` 外键 | 一次任务的多个执行步骤 |
| 传输任务或步骤 → 存储源 | `source_id`、`target_id` 普通字段，业务层校验 | 源目标定位，不自动获得外键级联保护 |
| 流程 → 节点、连线；节点 → 存储源 | `flow_id`、`node_key`、`source_id` 等业务引用 | 由 Service 维护引用有效性 |
| 生成字段 → 表配置 | `gen_table_column.table_id` 外键 | 一对多生成配置 |

`ModelMixin` 提供主键、UUID、软删除及时间字段，不单独建表。叠加 `UserMixin` 的实体还带 `created_id`、`updated_id`、`deleted_id`，外键指向 `sys_user.id`，用于后台操作人审计和部分数据范围查询。四张角色/岗位关联表直接继承 `MappedBase`，使用联合主键。

数据库外键的物理删除规则与业务软删除不同。例如评论外键声明级联删除，但实际通过接口软删除工单时，仍需由 Service 执行业务清理，不能仅凭外键推断接口的删除效果。部门数据范围不等于多租户隔离。

## 4. 框架维护的关系库表

这些表没有项目业务 `model.py`，不计入上述 29 张表。由框架创建不代表已向用户提供对应功能。

### 4.1 Alembic 与 APScheduler

| 表名 | 对应功能 | 建表或使用条件 |
| --- | --- | --- |
| `alembic_version` | 数据库结构迁移版本 | Alembic 执行升级、标记版本等操作时维护；不是产品版本管理 |
| `apscheduler_jobs` | §8 调度器的 SQLAlchemy jobstore | 调度器初始化并启动该 jobstore 时可创建；保存调度状态，不是节点定义或执行日志 |

当前调度器默认 jobstore 是 Redis，同时配置 SQLAlchemy 和内存 jobstore。即使默认任务不写关系库调度表，节点和执行日志仍可写业务表；表为空不能直接说明任务模块未工作。

### 4.2 Agno 表与 AI 对话

应用启用 `ai` 时，[AI 初始化代码](../backend/app/modules/ai/chat/crud.py) 使用与业务配置对应的数据库驱动，调用 Agno 的 `_create_all_tables()`。MySQL 使用配置的数据库，PostgreSQL 使用 `public` schema，SQLite 使用配置文件。

下表依据本机安装的 Agno **2.5.8** 默认表名及异步驱动建表清单；依赖升级后需重新核对，不能将本清单当作已连接数据库的查询结果。

| 默认表名 | 对应用途 | 当前驱动初始化情况 |
| --- | --- | --- |
| `agno_sessions` | §10 AI 会话、对话运行及消息数据；当前应用的主要 AI 持久化入口 | MySQL、PostgreSQL、SQLite |
| `agno_memories` | 框架用户记忆 | 三种驱动；不代表已提供独立记忆管理功能 |
| `agno_metrics` | 框架指标 | 三种驱动；不等于 §12 服务器监控表 |
| `agno_eval_runs` | 框架评估记录 | 三种驱动；无对应独立 PRD 功能 |
| `agno_knowledge` | 框架知识内容管理 | 三种驱动；不代表项目已实现知识库模块 |
| `agno_schema_versions` | Agno 内部表结构版本 | 三种驱动；不同于 `sys_version` 和 `alembic_version` |
| `agno_culture` | 框架文化或共享经验数据 | 本机 MySQL 驱动建表清单包含 |
| `agno_traces`、`agno_spans` | 框架执行追踪 | 本机 MySQL 驱动建表清单包含 |
| `agno_learnings` | 框架学习数据 | 本机 PostgreSQL、SQLite 驱动建表清单包含 |
| `agno_schedules`、`agno_schedule_runs` | 框架计划及运行数据 | 本机 PostgreSQL、SQLite 驱动建表清单包含；不属于项目 §8 APScheduler 实现 |
| `agno_approvals` | 框架审批数据 | 本机 PostgreSQL、SQLite 驱动建表清单包含；无对应独立 PRD 功能 |

AI 会话的 Agno `user_id` 当前使用后台用户名字符串，并以 `team_id = "default"` 等上下文隔离；它不是到 `sys_user.id` 的数据库外键。个人模型配置及激活项保存在 Redis，不在上述表中。

## 5. PRD 中没有独立业务表的功能

| PRD 功能 | 实际存储或复用关系 |
| --- | --- |
| §1、§2.5 前台用户能力与独立认证 | 需求方向待后续开发；当前未定义独立前台用户、身份绑定或会话业务表，不能把 `sys_user` 自动认作已完成隔离的前台账号表 |
| §3 认证 | 复用 `sys_user` 与 `sys_login_log`，Redis 存令牌、验证码和 `user_session`，不另建登录账号表 |
| §4.3 菜单与按钮权限 | 共用 `sys_menu`，不是菜单表和按钮表各一张 |
| §6 字典和参数读取 | 关系库保存定义，Redis 缓存供业务读取；缓存不是新增关系表 |
| §9.2 文件浏览 | 复用 `task_storage_node` 连接存储源，文件和目录实际保存在本地磁盘或远端存储 |
| §10 AI 模型配置 | Redis `ai_model_config` 按后台账号保存配置项与激活项 |
| §12 在线用户 | Redis `user_session`，强制下线撤销会话，没有独立在线用户表 |
| §12 健康检查、服务器资源、缓存监控 | 实时探测数据库、Redis、操作系统等，当前没有独立监控历史表 |
| §12 公共上传下载 | 文件系统及业务字段引用；当前没有统一附件表，上传本身不会自动插入逐文件记录 |
| 公告和传输进度 SSE | 事件推送与 Redis Pub/Sub；公告、传输结果仍以各自业务表为准，不另建 SSE 事件表 |

## 6. 初始化、模块开关与种子数据

表结构由 [模型发现](../backend/app/utils/import_util.py)、[数据库建表](../backend/app/core/database.py)、[初始化脚本](../backend/app/scripts/initialize.py) 和 Alembic 共同管理。当前为避免迁移误删表，模型元数据仍加载可选模块；因此关闭模块不等于删除其表，已有表也不能证明该模块路由当前启用。

| 初始化类别 | 表 |
| --- | --- |
| 基础种子 | `sys_menu`、`sys_dept`、`sys_param`、`sys_role`、`sys_dict_type`、`sys_dict_data`、`sys_user`、`sys_user_roles`、`sys_version` |
| 启用 task 时的种子 | `task_cornjob_node` |
| 启用 storage 时的种子 | `task_storage_node` |
| 无预置种子的 ORM 表 | 其余 ORM 表由相应操作写入；没有种子不代表不建表 |

种子位于 `backend/sql/<表名>.json`，目标表已有数据就整表跳过。Agno 和 APScheduler 的表由各自初始化机制维护，不通过上述 JSON 导入。

## 7. 维护说明

新增、删除或重命名 ORM 表，改变模块归属、关键关联或框架建表逻辑时，同步更新本文及 PRD 对应章节。本文记录当前实现映射；新文件表、前台用户表等尚未实现的设计应标为需求或方案，不混入现有表清单。
