# 数据表与 PRD 模块对应关系

本文按 [PRD](prd.md) 的模块划分，说明数据表承载的功能、关键关联和非关系库存储。整理日期：2026-10-26。

本文根据项目 ORM 与初始化代码静态梳理；历史 AI 表清单沿用移除前的 Agno 2.5.8 驱动核对结果，未连接开发库或线上库。以下是代码定义与建表逻辑的对应关系，不代表某个数据库当前已存在全部表；实际表清单还取决于数据库类型、初始化、迁移历史和模块运行情况。

## 1. 总览

项目在 `backend/app` 中显式定义了 **27 张 ORM 表**，包括实体表和关联表；不含 APScheduler、Alembic 等框架表及历史待清理表。

| 代码域 | 表数 | 对应 PRD |
| --- | --- | --- |
| `system` | 18 | §3 认证、§4 RBAC、§5 组织、§6 配置与字典、§7 内容与其他 |
| `task` | 2 | §8 定时任务 |
| `storage` | 4 | §9 文件存储管理 |
| `generator` | 2 | §10 代码生成 |
| `plugin/module_example` | 1 | §12 示例插件 |
| **合计** | **27** | 同一张表可被多个功能复用，不按页面重复计数 |

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

节点表定义“执行什么、何时执行”，不是服务器节点；执行日志表记录“某次执行结果”。任务表是唯一配置来源；定时任务采用单机单进程部署（一个后端实例、`WORKERS=1`），运行计划只保存在内存，启动时重新加载。

### 2.6 文件存储管理

| 表名 | PRD 模块 | 承载功能与关键关联 | 模型源码 |
| --- | --- | --- | --- |
| `task_storage_node` | §9.1 存储节点 | 存储位置、协议、加密凭据、公有访问根地址、启停 | [node/model.py](../backend/app/modules/storage/node/model.py) |
| `storage_setting` | §9.1 默认设置 | 单例 `id=1`，`default_node_id` 外键关联唯一默认节点 | [node/model.py](../backend/app/modules/storage/node/model.py) |
| `storage_file` | §9.3 公有附件 | 上传人、节点、对象路径、元数据、SHA1、上传次数、最后上传时间、可空的唯一 `dedup_key`；关联节点和后台上传管理员 | [file/model.py](../backend/app/modules/storage/file/model.py) |
| `storage_file_reference` | §9.4 业务引用 | 复合主键为文件 ID、业务类型、业务 ID 和字段；由已完成授权的业务服务在自身事务维护 | [file/model.py](../backend/app/modules/storage/file/model.py) |

文件浏览查询实际存储；附件管理查询文件记录。现有业务 URL 字段保留，新业务保存文件 ID 并同步维护引用。逻辑删除保留实际对象和原公有链接。

### 2.7 代码生成与示例插件

| 表名 | PRD 模块 | 承载功能与关键关联 | 模型源码 |
| --- | --- | --- | --- |
| `gen_table` | §10 代码生成 | 表级生成配置；目标表、实体、主子表关系与父菜单选择 | [gencode/model.py](../backend/app/modules/generator/gencode/model.py) |
| `gen_table_column` | §10 代码生成 | `table_id` 外键关联表配置；数据库字段、代码映射和表单、列表、查询配置 | [gencode/model.py](../backend/app/modules/generator/gencode/model.py) |
| `example_demo` | §12 示例插件 | 插件加载与通用 CRUD 的演示记录，不承担产品业务 | [demo/model.py](../backend/app/plugin/module_example/demo/model.py) |

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
| 默认设置 → 节点；附件 → 节点；业务引用 → 附件 | `default_node_id`、`storage_node_id`、`file_id` 外键 | 默认配置、对象定位与引用保护 |
| 生成字段 → 表配置 | `gen_table_column.table_id` 外键 | 一对多生成配置 |

`ModelMixin` 提供主键、UUID、软删除及时间字段，不单独建表。叠加 `UserMixin` 的实体还带 `created_id`、`updated_id`、`deleted_id`，外键指向 `sys_user.id`，用于后台操作人审计和部分数据范围查询。四张角色/岗位关联表直接继承 `MappedBase`，使用联合主键。

数据库外键的物理删除规则与业务软删除不同。例如评论外键声明级联删除，但实际通过接口软删除工单时，仍需由 Service 执行业务清理，不能仅凭外键推断接口的删除效果。部门数据范围不等于多租户隔离。

## 4. 框架维护的关系库表

这些表没有项目业务 `model.py`，不计入上述 29 张表。由框架创建不代表已向用户提供对应功能。

### 4.1 Alembic 与 APScheduler

| 表名 | 对应功能 | 建表或使用条件 |
| --- | --- | --- |
| `alembic_version` | 数据库结构迁移版本 | Alembic 执行升级、标记版本等操作时维护；不是产品版本管理 |
| `apscheduler_jobs` | 已移除的 SQLAlchemy jobstore 历史表 | 当前不再创建或访问；旧部署可能存在，待确认后删除，未执行 |

当前只使用 MemoryJobStore 和线程池。任务定义持久化在 `task_cornjob_node`，执行记录持久化在 `task_corn_job`；运行计划不再写数据库或 Redis。

### 4.2 已移除 AI 模块：待删除表和历史数据

**状态：代码已移除，以下数据库及 Redis 清理均未执行。** 不再初始化或访问 AI 数据。下表为旧版 Agno 2.5.8 的默认表名候选，实际是否存在取决于数据库类型及历史初始化；清理前应核对实际库及是否被其他应用复用。

| 待删除表名 | 历史用途 | 旧驱动建表范围 | 清理状态 |
| --- | --- | --- | --- |
| `agno_sessions` | 会话、运行与消息 | MySQL、PostgreSQL、SQLite | 待删除，未执行 |
| `agno_memories` | 用户记忆 | 三种驱动 | 待删除，未执行 |
| `agno_metrics` | 框架指标 | 三种驱动 | 待删除，未执行 |
| `agno_eval_runs` | 评估记录 | 三种驱动 | 待删除，未执行 |
| `agno_knowledge` | 知识内容 | 三种驱动 | 待删除，未执行 |
| `agno_schema_versions` | 框架表结构版本 | 三种驱动 | 待删除，未执行 |
| `agno_culture` | 共享经验 | MySQL | 待删除，未执行 |
| `agno_traces`、`agno_spans` | 执行追踪 | MySQL | 待删除，未执行 |
| `agno_learnings` | 学习数据 | PostgreSQL、SQLite | 待删除，未执行 |
| `agno_schedules`、`agno_schedule_runs` | 框架计划及运行 | PostgreSQL、SQLite | 待删除，未执行 |
| `agno_approvals` | 框架审批 | PostgreSQL、SQLite | 待删除，未执行 |

以下只清理相关记录，**保留共享表和其他业务数据**：

| 存储位置 | 待清理范围 | 清理状态 |
| --- | --- | --- |
| `sys_menu` | 旧 `route_name=AI`、`route_path=/ai` 目录及其后代菜单、`module_ai:*` 按钮权限；新种子已移除，但不会更新非空旧表 | 待清理记录，未执行 |
| `sys_role_menus` | 仅指向上述菜单 ID 的角色授权关联；先清关联，再按子节点到父节点清理菜单 | 待清理记录，未执行 |
| Redis | `ai_model_config:items:*`、`ai_model_config:active:*`、`ai_model_config:lock:*` | 待清理键，未执行 |
| 后台登录会话和浏览器缓存 | 旧会话、工作标签可能缓存菜单或旧地址；清理菜单后重新登录、清理相关标签刷新 | 未执行 |

`sys_version`、`alembic_version` 及 29 张业务 ORM 表均不属于 AI 模块待删除表。`apscheduler_jobs` 的后续单机重构处理见 §4.3。旧会话以用户名关联后台账号，不需要删除 `sys_user`。本次未连接数据库或 Redis，未生成或执行删表迁移。

### 4.3 定时任务单机化：选主数据清理范围

**状态：选主、续期、候选争抢与故障接管代码已移除；经用户授权，开发库任务字段迁移已核对到 `6e9cd5b5bb23`，Redis 未连接或清理。** 经模型、迁移与调度代码核对，多节点选主只使用 Redis 锁，仓库没有专用的服务器节点表、主节点表或选主记录表，选主本身无专用表可删；以下历史 JobStore 数据因本次进一步改为内存调度而列为待清理。

| 表或存储 | 处理结果 | 原因及清理状态 |
| --- | --- | --- |
| `task_cornjob_node` | 保留表和数据 | 保存任务函数、参数及执行计划，不是服务器节点 |
| `task_corn_job` | 保留表和数据 | 保存单机任务执行日志 |
| `apscheduler_jobs` | 待删除，未执行 | SQLAlchemy jobstore 已移除；停用旧部署并核对任务定义后可删除 |
| Redis `fastapiadmin:scheduler:lock` | 不再创建或访问 | 旧选主锁带 30 秒 TTL，旧进程全部停止后自然过期；未手动删除 |
| Redis `scheduler_job_lock` | 移除废弃键枚举 | 当前代码原本已无调用；如历史环境遗留该键，可在旧进程全部停止后定向删除，未执行 |
| Redis `apscheduler.jobs`、`apscheduler.run_times` | 待定向删除，未执行 | 旧 jobstore 数据，当前不再读写；须停用旧进程并确认未被其他应用共用后清理 |

调度器监控只读正式计划和日志，支持全局暂停/恢复；任务管理统一维护定义、启停与手动执行。启用 task 模块时要求 `WORKERS=1`，部署只运行一个后端实例；不再维护主备状态或提供自动接管。

### 4.4 单机调度重构：字段迁移

- `task_cornjob_node` 移除 `jobstore`、`executor` 模型字段与 API/UI 选项。开发库旧列已删除并核对；其余任务定义保留。
- `task_corn_job` 新增可空 `started_time`、`finished_time`、`duration_ms`；历史日志的新增时间和耗时允许为空。移除重复的 `next_run_time` 和调度快照 `job_state` 模型字段；开发库旧列已删除并核对。
- 菜单种子将定时任务的“节点管理”改为“任务管理”，保留 `route_name=Node` 和原组件路径；移除 `module_task:cronjob:job:task` 权限种子。旧 `sys_menu` 的名称与该权限及 `sys_role_menus` 关联仅标记待定向清理，未修改数据库；非空表不会被新种子覆盖。
- 用户确认开发服务正在运行，工作区出现自动生成的迁移 `2026_10_26_2319_6e9cd5b5bb23.py`。经授权执行 `main.py upgrade --env=dev` 后核对：开发库版本为 `6e9cd5b5bb23`，三个新增日志字段存在、四个旧字段已删除。未另外启动或重启服务。其他部署仍须按实际库结构审核并应用迁移。
- 当前 dev 自动迁移拦截只匹配 `op.drop_*`，无法覆盖该迁移中的 `batch_op.drop_column`；不能依赖它阻止删列。本次未修改通用迁移机制，迁移文件原样保留。

新增字段审核参考 SQL（仅针对缺少这些列的旧库，实际迁移应按部署数据库生成）：

```sql
ALTER TABLE task_corn_job ADD COLUMN started_time TIMESTAMP NULL;
ALTER TABLE task_corn_job ADD COLUMN finished_time TIMESTAMP NULL;
ALTER TABLE task_corn_job ADD COLUMN duration_ms FLOAT NULL;
```

重启不补跑停机期间错过的任务，过期 date 计划跳过；interval 有开始时间则沿用，否则从启动时重新计时。运行中调度使用统一的 60 秒迟到宽限。上次异常退出留下的执行中日志在启动时标记为已取消，不自动重试。

## 5. PRD 中没有独立业务表的功能

| PRD 功能 | 实际存储或复用关系 |
| --- | --- |
| §1、§2.5 前台用户能力与独立认证 | 需求方向待后续开发；当前未定义独立前台用户、身份绑定或会话业务表，不能把 `sys_user` 自动认作已完成隔离的前台账号表 |
| §3 认证 | 复用 `sys_user` 与 `sys_login_log`，Redis 存令牌、验证码和 `user_session`，不另建登录账号表 |
| §4.3 菜单与按钮权限 | 共用 `sys_menu`，不是菜单表和按钮表各一张 |
| §6 字典和参数读取 | 关系库保存定义，Redis 缓存供业务读取；缓存不是新增关系表 |
| §9.2 文件浏览 | 复用 `task_storage_node` 只读浏览实际磁盘/远端内容，上传进入统一附件服务 |
| §11 在线用户 | Redis `user_session`，强制下线撤销会话，没有独立在线用户表 |
| §11 健康检查、服务器资源、缓存监控 | 实时探测数据库、Redis、操作系统等，当前没有独立监控历史表 |
| §11 公共上传下载 | 默认节点实际对象与 `storage_file` 台账；旧业务 URL 保留，新业务通过文件 ID 引用 |
| 公告 SSE | 事件推送与 Redis Pub/Sub；公告仍以业务表为准，不另建 SSE 事件表 |

## 6. 初始化、模块开关与种子数据

表结构由 [模型发现](../backend/app/utils/import_util.py)、[数据库建表](../backend/app/core/database.py)、[初始化脚本](../backend/app/scripts/initialize.py) 和 Alembic 共同管理。当前为避免迁移误删表，模型元数据仍加载可选模块；因此关闭模块不等于删除其表，已有表也不能证明该模块路由当前启用。

| 初始化类别 | 表 |
| --- | --- |
| 基础种子 | `sys_menu`、`sys_dept`、`sys_param`、`sys_role`、`sys_dict_type`、`sys_dict_data`、`sys_user`、`sys_user_roles`、`sys_version` |
| 启用 task 时的种子 | `task_cornjob_node` |
| 启用 storage 时的种子 | `task_storage_node` |
| 无预置种子的 ORM 表 | 其余 ORM 表由相应操作写入；没有种子不代表不建表 |

种子位于 `backend/sql/<表名>.json`，目标表已有数据就整表跳过。当前不再初始化 APScheduler 持久化表或 Redis 计划；启动时从任务定义表重建内存计划。已移除 AI 模块的历史清理范围见 §4.2。

## 7. 维护说明

新增、删除或重命名 ORM 表，改变模块归属、关键关联或框架建表逻辑时，同步更新本文及 PRD 对应章节。本文记录当前实现映射；新文件表、前台用户表等尚未实现的设计应标为需求或方案，不混入现有表清单。

### 6. 文件存储迁移与历史清理

- 迁移链保留开发服务自动生成的 `68a3f2e39fc6`（新增附件/默认配置/引用表及节点公有地址、移除 `is_default`），补充迁移 `c8a4e710b632` 初始化默认指针、公有本地地址与附件菜单，旧流程/传输菜单逻辑隐藏，新权限由管理员分配。
- 五张历史表 `task_storage_transfer`、`task_storage_transfer_step`、`task_storage_workflow`、`task_storage_workflow_node`、`task_storage_workflow_edge` 不再属于 ORM，保留数据库数据，未自动删除。
- 开发库经授权已迁移并核对版本 `c8a4e710b632`、默认节点 1、公有地址 `/static/upload` 与附件菜单；其他部署仍需应用迁移。MySQL 不支持上传人互斥 CHECK 与 SET NULL 外键组合，互斥由上传服务保证。
- 不导入、迁移或清理旧磁盘文件；旧业务 URL 字段继续可用。独立前台用户表尚未实现，`storage_file.user_id` 暂不设置外键。

### 7. 上传链路收敛与指纹去重

- `923815682316` 增加可空唯一 `dedup_key`；`f621b9a0d745` 为历史可用附件回填指纹，同内容多条记录只选一条规范记录，不合并文件 ID；`211b105f74ea` 删除已被替代的 `ix_storage_file_dedup` 复合索引。无附件或实际文件删除。
- 指纹涵盖节点、管理员/前台用户、分类、SHA1 和大小。停用、逻辑删除释放指纹；并发上传由唯一约束收敛，重复对象补偿清理。
- 默认节点只通过专用操作修改，节点编辑不接收默认标记；存储定位变化在节点管理和上传登记阶段使用同一规则检查。
- 开发库经已授权的 upgrade 与只读核对，版本为 `211b105f74ea`，唯一指纹约束存在，旧复合索引已移除，默认节点保持 1；其他部署仍需迁移。
