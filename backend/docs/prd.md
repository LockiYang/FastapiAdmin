# FastapiAdmin 后端产品需求文档

> 文档基线：当前仓库的后端实现。业务范围以本文件为准；接口行为以 `backend/app/` 中的 Controller、Schema、Service 和 Model 为核对依据。

## 1. 产品概述

### 1.1 产品目标

FastapiAdmin 为一个管理后台提供账号登录、组织与权限管理、内容配置、工单、任务调度、文件存储与传输、AI 对话、代码生成和运行监控。后端向管理端、移动端及其他 API 客户端提供接口。用户以角色获得功能权限；部分业务数据按创建人或部门控制可见范围。

### 1.2 使用者

| 使用者 | 工作场景 |
| --- | --- |
| 超级管理员 | 管理全平台账号、角色、菜单及运行资源；通用功能权限和数据范围校验对其放行。 |
| 后台管理员 | 在已授权功能内管理用户、部门、公告、工单及扩展模块。 |
| 普通用户 | 登录、维护个人信息、查看获授权的数据并使用业务功能。 |
| 访客 | 使用登录、验证码、注册和已发布版本查询等开放接口。 |

### 1.3 功能地图

| 业务域 | 功能 |
| --- | --- |
| 系统 | 认证、用户、角色、菜单、部门、岗位、字典、参数、公告、工单、版本、日志 |
| 任务 | 定时任务节点、调度器、执行日志、存储源、文件浏览、文件传输、传输流程 |
| 智能与开发 | AI 聊天、用户模型配置、代码生成、示例插件 |
| 运维与公共服务 | 健康检查、在线会话、缓存监控、服务器信息、基础统计、文件上传下载 |

## 2. 通用产品规则

### 2.1 接口与响应约定

- 后端路由按 `/system`、`/task`、`/ai`、`/generator`、`/monitor`、`/common` 聚合；部署时对外访问地址通常带 `/api/v1` 前缀。下文接口路径从业务域开始写。
- 普通 JSON 接口返回 `code`、`msg`、`data`、`status_code`、`success`；文件下载、SSE 和 WebSocket 使用各自的协议响应。
- 分页请求通用参数为 `page_no`（默认 1）、`page_size`（默认 10，最大 100）、`order_by`；分页结果含 `page_no`、`page_size`、`total`、`has_next`、`items`。
- 通用业务表带 `id`、`uuid`、创建/更新时间及软删除字段。使用 `UserMixin` 的表另带创建、更新、删除人 ID。
- 业务接口通过请求级数据库事务执行，成功后提交，异常回滚；通用 CRUD 的创建操作填充创建人与更新人。

### 2.2 认证、功能权限和数据范围

**超管身份由用户的 `is_superuser=true` 决定**，它会绕过角色权限和数据范围检查，角色统一按菜单、按钮和数据范围授权。

1. 账号密码登录成功后签发访问令牌和刷新令牌，并在 Redis 保存会话。请求认证同时校验令牌、Redis 会话及数据库中的用户状态。
2. 角色关联菜单；启用角色下的启用菜单提供 `permission` 标识。受保护接口通过 `AuthPermission` 校验标识。超级管理员跳过该校验。
3. 角色数据范围 `data_scope`：`1` 仅本人创建的数据；`2` 当前用户所属部门及子部门成员创建的数据；`3` 全部数据。多角色并存时，`3` 优先，其次 `2`，否则按本人范围。
4. 通用 CRUD 的读取、分页、统计及普通单条更新的对象预读取使用数据范围条件。用户表的部门范围按用户自身 `dept_id` 过滤；其他带创建人关系的模型按创建人的部门过滤。
5. 通用批量写入方法 `set`、`delete` 不自行附加数据范围条件；各业务 Service 的存在性和授权检查以实际实现为准。

### 2.3 状态与授权约定

- 用户、角色、部门、岗位、菜单等通用状态采用 `0=启用`、`1=停用`，具体模块另有状态定义时以模块规则为准。
- 后台操作由对应接口的权限标识控制。角色授权接口使用 `module_system:role:permission`；上传、下载、任务调度和缓存清理等操作有独立权限标识。
- 当前用户信息接口返回可见菜单树；管理端菜单按 `scope=web` 读取。

## 3. 系统管理

### 3.1 认证与会话

**业务目标**：验证用户身份、维持会话，并支持账号密码、第三方及微信小程序登录。

**主要数据**：`sys_user` 存账号和密码哈希；`sys_login_log` 存登录结果；Redis 存会话、访问令牌、刷新令牌和验证码状态。JWT 的 `sub` 是会话 ID。

**业务规则**：

1. 账号密码登录检查用户是否存在、密码是否正确及账号是否停用；可按配置启用滑块验证码。登录请求对非本地 IP 做 Redis 固定窗口限流。
2. 成功登录记录时间、IP、地点、操作系统和浏览器，生成两个令牌；失败登录记录失败日志。刷新接口轮换刷新令牌，已失效的旧刷新令牌再次使用会撤销会话。
3. 退出登录删除该会话在 Redis 中的访问令牌、刷新令牌和会话信息。
4. OAuth 支持 GitHub、Gitee、QQ、微信开放平台；微信小程序支持 code 登录、手机号登录及小程序码生成。第三方能力依赖部署凭据。
5. 验证码获取、滑块完成和账号密码登录使用同一验证码状态；验证码是否启用由配置决定。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/system/auth/login` | 账号密码登录 |
| POST | `/system/auth/token/refresh` | 刷新访问与刷新令牌 |
| GET / POST | `/system/auth/captcha/get`、`/system/auth/captcha/slider/complete` | 获取并完成滑块验证码 |
| POST | `/system/auth/logout` | 退出当前会话 |
| GET | `/system/auth/oauth/{provider}/login`、`/system/auth/oauth/{provider}/callback` | 第三方授权与回调 |
| POST | `/system/auth/wx-login`、`/system/auth/wx-phone-login`、`/system/auth/wx-qrcode/generate` | 微信小程序登录、手机号登录及小程序码 |

### 3.2 用户与个人资料

**业务目标**：维护账号档案、部门和角色关系，提供个人资料维护与 Excel 批量处理。

**数据模型**：`sys_user` 的核心字段为 `username`、`password`、`name`、`mobile`、`email`、`gender`、`avatar`、`status`、`is_superuser`、`dept_id`、`last_login`；`sys_user_roles`、`sys_user_positions` 记录多对多关系。

**业务规则**：

1. 管理员可按条件查询、创建、修改、删除、启停用户，指定部门、角色和岗位。用户名在数据库中唯一；角色或岗位分配时校验目标存在且启用。
2. 当前用户可查询个人信息和可见菜单、更新基本资料、使用旧密码修改密码。管理员重置其他用户密码时不得重置超级管理员密码。
3. 删除用户前校验用户存在；超级管理员和当前登录用户不能删除。删除时先解除角色、岗位关系，再执行软删除。
4. 注册接口创建启用的普通账号；注册用户的创建人与更新人标记为自身。忘记密码接口接收用户名申请，不直接修改密码。
5. 支持下载导入模板、导入用户数据和按查询结果导出 Excel；导入失败时返回对应错误信息。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET / PUT | `/system/user/current/info`、`/system/user/current/info/update` | 当前用户资料与菜单、修改资料 |
| PUT | `/system/user/password/change`、`/system/user/password/reset/{id}` | 修改本人密码、管理员重置密码 |
| POST | `/system/user/password/forget`、`/system/user/register` | 忘记密码申请、注册 |
| GET | `/system/user/list`、`/system/user/detail/{id}` | 分页与详情 |
| POST / PUT / DELETE / PATCH | `/system/user/create`、`/system/user/update/{id}`、`/system/user/delete`、`/system/user/status/batch` | 管理用户 |
| GET / POST | `/system/user/import/template`、`/system/user/import/data`、`/system/user/export` | 模板、导入和导出 |

### 3.3 角色与菜单授权

**业务目标**：以角色组合可调用的功能和可见的数据范围。

**数据模型**：`sys_role` 保存 `name`、唯一 `code`、`status`、`order`、`data_scope`；`sys_role_menus` 保存角色与菜单关系；`sys_menu` 保存菜单树、类型、权限标识、路由、图标、显示和缓存等配置。

**业务规则**：

1. 创建或编辑角色时检查名称和编码重复。角色可批量启停，并导出 Excel；选项接口返回可用角色。
2. 角色授权一次提交角色 ID、菜单 ID 和 `data_scope`，替换角色菜单关系并保存数据范围。菜单 ID 与角色 ID 必须存在。
3. 菜单类型为 `1=目录`、`2=菜单`、`3=按钮`、`4=外链`。目录下可放目录、菜单或外链；菜单下可放按钮；子菜单的可见范围与父菜单一致。
4. 删除菜单会连同其后代处理；批量启用菜单时联动祖先，批量停用时联动子孙。角色权限只收集启用角色下的启用菜单。
5. 角色仍关联有效用户时禁止删除，须先解除用户角色关联。有效用户指未删除的用户，包含已停用账号；仅关联已删除用户不阻止删除。批量删除中任一角色不满足此条件时整批拒绝。编辑用户时明确提交空角色列表可清除全部角色关联，未提交角色字段或提交 `null` 则保持原有授权。
6. 数据范围查询只采用未删除且启用（`is_deleted=false`、`status=0`）角色的 `data_scope`，已删除、已停用角色不参与数据范围计算；多角色范围优先级仍按 §2.2 执行。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/system/role/list`、`/system/role/detail/{id}`、`/system/role/options` | 角色查询与选项 |
| POST / PUT / DELETE / PATCH | `/system/role/create`、`/system/role/update/{id}`、`/system/role/delete`、`/system/role/status/batch` | 角色维护 |
| PUT / POST | `/system/role/permission`、`/system/role/export` | 菜单及数据范围授权、导出 |
| GET | `/system/menu/tree`、`/system/menu/detail/{id}` | 菜单树与详情 |
| POST / PUT / DELETE / PATCH | `/system/menu/create`、`/system/menu/update/{id}`、`/system/menu/delete`、`/system/menu/status/batch` | 菜单维护 |

### 3.4 部门与岗位

**业务目标**：维护组织树和岗位目录，作为用户归属及部门数据范围的基础。

**数据模型**：`sys_dept` 包含唯一 `code`、`name`、`parent_id`、`order`、`status`；`sys_position` 包含唯一 `code`、`name`、`order`、`status`。用户最多关联一个部门，可关联多个岗位。

**业务规则**：部门支持树形查询；存在子部门时拒绝删除父部门。部门批量启用时联动上级，停用时联动下级。岗位支持按状态获取下拉选项及 Excel 导出。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/system/dept/tree`、`/system/dept/detail/{id}` | 部门树与详情 |
| POST / PUT / DELETE / PATCH | `/system/dept/create`、`/system/dept/update/{id}`、`/system/dept/delete`、`/system/dept/status/batch` | 部门维护 |
| GET | `/system/position/list`、`/system/position/detail/{id}`、`/system/position/options` | 岗位查询 |
| POST / PUT / DELETE / PATCH | `/system/position/create`、`/system/position/update/{id}`、`/system/position/delete`、`/system/position/status/batch` | 岗位维护 |
| POST | `/system/position/export` | 导出岗位 |

### 3.5 字典与系统参数

**业务目标**：维护页面选项和系统配置，并通过 Redis 提供快速读取。

**数据模型**：`sys_dict_type` 记录名称、唯一类型编码和状态；`sys_dict_data` 记录类型、标签、值、排序、默认项、展示样式和状态；`sys_param` 记录参数名称、键、值、内置标记及状态。

**业务规则**：字典类型与条目可分别查询、增删改和批量启停；按字典类型编码读取条目。应用启动时初始化字典缓存。系统参数修改时不允许变更 `config_key`，保存后同步 Redis；参数信息接口从缓存读取。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/system/dict/type/detail/{id}`、`/system/dict/type/list`、`/system/dict/type/optionselect` | 字典类型查询 |
| POST / PUT / DELETE / PATCH | `/system/dict/type/create`、`/system/dict/type/update/{id}`、`/system/dict/type/delete`、`/system/dict/type/status/batch` | 字典类型维护 |
| GET | `/system/dict/data/detail/{id}`、`/system/dict/data/list`、`/system/dict/data/info/{dict_type}` | 字典条目查询 |
| POST / PUT / DELETE / PATCH | `/system/dict/data/create`、`/system/dict/data/update/{id}`、`/system/dict/data/delete`、`/system/dict/data/status/batch` | 字典条目维护 |
| GET / PUT | `/system/param/info`、`/system/param/update/{id}` | 读取和修改系统参数 |

### 3.6 公告与通知流

**业务目标**：发布和维护通知公告，并在变更时提示在线客户端刷新。

**数据模型**：`sys_notice` 包含 `notice_title`、`notice_type`（`1=通知`、`2=公告`）、`notice_content`、`status`、备注和审计字段。状态字段定义为 `0=草稿`、`1=已发布`、`2=已归档`。

**业务规则**：标题不能为空，内容会做 HTML 清理；标题重复时创建或修改被拒绝。公告列表支持条件查询，创建、更新、启停时通过 SSE 广播 `notice_update` 轻量事件，客户端收到后重新获取列表。`/available` 当前按 `status=0` 返回最多 10 条。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/system/notice/list`、`/system/notice/detail/{id}`、`/system/notice/available` | 公告查询 |
| POST / PUT / DELETE / PATCH | `/system/notice/create`、`/system/notice/update/{id}`、`/system/notice/delete`、`/system/notice/status/batch` | 公告维护 |
| GET | `/system/notice/stream` | 公告变更 SSE |

### 3.7 工单与评论

**业务目标**：收集建议和缺陷反馈，并支持指派、处理、回复和讨论。

**数据模型**：`sys_ticket` 包含标题、类型（`suggestion`/`bug`/`optimize`/`other`）、内容、摘要、图片、处理人、回复及状态；`sys_ticket_comment` 包含工单 ID 和评论内容。工单状态为 `0=待处理`、`1=处理中`、`2=已完成`、`3=已关闭`。

**状态规则**：

| 原状态 | 目标状态 | 可操作人 |
| --- | --- | --- |
| 待处理 | 处理中 | 创建人、处理人、超级管理员 |
| 待处理 | 已关闭 | 创建人、超级管理员 |
| 处理中 | 已完成 | 处理人、超级管理员 |
| 处理中 | 已关闭 | 创建人、处理人、超级管理员 |
| 已完成 | 已关闭 | 创建人、超级管理员 |
| 已关闭 | 待处理 | 超级管理员 |

**其他规则**：更改处理人时先校验目标用户可查询；批量更新会逐条校验状态流转。状态统计分别计算待处理、处理中、已完成。评论创建前确认工单存在。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/system/ticket/stats`、`/system/ticket/list`、`/system/ticket/detail/{id}` | 统计、分页及详情 |
| POST / PUT / DELETE | `/system/ticket/create`、`/system/ticket/update/{id}`、`/system/ticket/batch`、`/system/ticket/delete` | 创建、更新、批量状态操作和删除 |
| POST | `/system/ticket/export` | 导出工单 |
| GET / POST | `/system/ticket/{ticket_id}/comments` | 评论分页与新增 |

### 3.8 版本和日志

**版本管理**：`sys_version` 记录唯一版本号、标题、日期、内容、排序、状态（`0=草稿`、`1=已发布`、`2=已回滚`）及是否要求重新登录。后台可分页、查看、增删改和修改状态；已发布列表接口按 `status=1` 返回。

**日志管理**：`sys_login_log` 记录成功/失败及 IP、地点、客户端信息；`sys_operation_log` 记录请求路径、方法、请求内容、响应、耗时与操作人。后台可查询和删除登录日志，查询、删除、导出操作日志。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/system/versions/list`、`/system/versions/detail/{id}`、`/system/versions/published` | 版本分页、详情与已发布列表 |
| POST / PUT / DELETE | `/system/versions/create`、`/system/versions/update/{id}`、`/system/versions/delete`、`/system/versions/{id}/status` | 版本维护与状态变更 |
| GET / DELETE | `/system/log/login/list`、`/system/log/login/detail/{id}`、`/system/log/login/delete` | 登录日志查询和删除 |
| GET / DELETE / POST | `/system/log/operation/list`、`/system/log/operation/detail/{id}`、`/system/log/operation/delete`、`/system/log/operation/export` | 操作日志查询、删除和导出 |

## 4. 定时任务与存储业务

### 4.1 定时任务节点和执行日志

**业务目标**：维护可手动或按计划执行的任务节点，查看执行结果，并对调度器和任务进行运维控制。

**数据模型**：`task_cornjob_node` 保存名称、唯一编码、处理函数、触发方式及参数、执行器、任务存储器、起止时间、状态；`task_corn_job` 保存任务 ID、触发方式、执行状态、结果和错误。执行状态为 `0=待执行`、`1=执行中`、`2=成功`、`3=失败`、`4=超时`、`5=取消`。

**业务规则**：

1. 节点的 `func` 必填。处理函数可用 `builtin:` 内置处理器标识；原始代码块执行受 `SCHEDULER_ALLOW_CODE_EXEC` 配置控制。
2. 触发器可选 `cron`、`interval`、`date`；设置触发器时必须填写触发参数。留空可只保存节点并通过手动执行接口运行。
3. 节点可设置合并执行和最大并发实例数；列表响应可展示下一次、最近一次运行时间及不可调度原因。
4. 调度器接口支持启动、暂停、恢复、关闭、查看任务清单和控制台；任务接口支持暂停、恢复、立即运行、修改、移除。执行日志支持分页、详情和删除。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/task/cronjob/node/options`、`/task/cronjob/node/list`、`/task/cronjob/node/detail/{id}` | 节点选项、分页及详情 |
| POST / PUT / DELETE / PATCH | `/task/cronjob/node/create`、`/task/cronjob/node/update/{id}`、`/task/cronjob/node/delete`、`/task/cronjob/node/clear`、`/task/cronjob/node/status/batch` | 节点维护 |
| POST | `/task/cronjob/node/execute/{id}` | 手动执行节点 |
| GET | `/task/cronjob/job/scheduler/status`、`/task/cronjob/job/scheduler/jobs`、`/task/cronjob/job/scheduler/console` | 调度器状态、任务和控制台 |
| POST / DELETE | `/task/cronjob/job/scheduler/start`、`/task/cronjob/job/scheduler/pause`、`/task/cronjob/job/scheduler/resume`、`/task/cronjob/job/scheduler/shutdown`、`/task/cronjob/job/scheduler/jobs/clear` | 控制调度器 |
| POST / PUT / DELETE | `/task/cronjob/job/task/pause/{job_id}`、`/task/cronjob/job/task/resume/{job_id}`、`/task/cronjob/job/task/run/{job_id}`、`/task/cronjob/job/task/modify/{job_id}`、`/task/cronjob/job/task/remove/{job_id}` | 控制单个任务 |
| GET / DELETE | `/task/cronjob/job/log/list`、`/task/cronjob/job/log/detail/{id}`、`/task/cronjob/job/log/delete` | 执行日志 |

### 4.2 存储源与文件浏览

**业务目标**：用统一方式管理本地、文件服务器和对象存储中的文件。

**数据模型**：`task_storage_node` 保存名称、协议、连接地址、端口、账号、加密保存的凭据、桶、区域、路径前缀、分片配置、默认标记和状态。支持 `local`、`ftp`、`ftps`、`sftp`、`s3`、`obs`、`oss`、`cos`。

**业务规则**：

1. 创建或修改存储源时按协议校验连接字段；可用保存的源或临时配置测试连接。调用方未指定源时优先选默认启用源，再选其他启用源。
2. 对象存储需提供桶信息；各协议的 endpoint、region 等必填条件由配置校验决定。连接密码对外响应不以明文提供。
3. 文件浏览支持列表、桶列表、上传、文件下载、目录打包下载、删除、复制/移动、重命名、创建目录和分享链接。操作必须基于可用存储源和有效路径。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/task/storage/node/protocols`、`/task/storage/node/advanced-fields` | 协议及高级配置定义 |
| GET | `/task/storage/node/page`、`/task/storage/node/list`、`/task/storage/node/detail/{id}` | 存储源查询 |
| POST / PUT / DELETE | `/task/storage/node/create`、`/task/storage/node/update/{id}`、`/task/storage/node/delete` | 存储源维护 |
| POST | `/task/storage/node/test`、`/task/storage/node/test/{id}` | 测试临时配置或已有源 |
| GET | `/task/storage/browse/list`、`/task/storage/browse/buckets` | 文件与桶列表 |
| POST | `/task/storage/browse/upload`、`/task/storage/browse/download`、`/task/storage/browse/download_dir` | 上传、下载文件或 ZIP 目录 |
| DELETE / POST / PUT | `/task/storage/browse/delete`、`/task/storage/browse/copy`、`/task/storage/browse/rename`、`/task/storage/browse/mkdir`、`/task/storage/browse/share` | 文件及目录操作 |

### 4.3 文件传输任务

**业务目标**：将本地上传文件或远端文件传输至一个或多个目标存储源，并展示实时进度。

**数据模型**：`task_storage_transfer` 保存任务名称、源类型、源地址、任务类型、状态、大小、速度、进度和错误；`task_storage_transfer_step` 保存每个目标步骤的源与目标、传输方式和步骤进度。任务类型为 `parallel`（多目标）或 `chain`（链式）；状态为 `pending`、`running`、`success`、`failed`、`canceled`。

**业务规则**：

1. 远端任务指定源存储源与路径；本地任务先上传文件到服务端临时文件。至少指定一个目标，目标必须存在且启用。
2. 并行模式的每个步骤都读取原始源；链式模式的后一步读取前一步目标。可选流式或分片传输及分片参数。
3. 创建任务先保存任务和步骤，在请求事务提交后启动后台传输。列表与详情返回步骤和进度；取消、删除按当前任务状态执行；SSE 推送进度事件。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/task/storage/transfer/task`、`/task/storage/transfer/task/upload` | 创建远端或本地源传输任务 |
| GET | `/task/storage/transfer/task/page`、`/task/storage/transfer/task/{id}` | 分页及详情 |
| POST / DELETE | `/task/storage/transfer/task/{id}/cancel`、`/task/storage/transfer/task` | 取消和删除任务 |
| GET | `/task/storage/transfer/stream` | 传输进度 SSE |

### 4.4 存储传输流程

**业务目标**：保存可重复执行的存储源连线，执行时批量创建传输任务。

**数据模型**：`task_storage_workflow` 保存流程名称、类型、画布图和状态；节点表保存存储源与默认路径，连线表保存源/目标节点、启用标记、传输方式和分片参数。

**业务规则**：流程创建或编辑时解析画布节点与连线并落库。执行时读取启用的连线，按连线生成传输计划；可在请求中覆盖源路径。没有启用连线、节点无效、源与目标相同或缺少路径时拒绝执行。执行结果返回创建的传输任务 ID 列表。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/task/storage/workflow/page`、`/task/storage/workflow/list`、`/task/storage/workflow/detail/{id}` | 流程查询 |
| POST / PUT / DELETE | `/task/storage/workflow/create`、`/task/storage/workflow/update/{id}`、`/task/storage/workflow/delete` | 流程维护 |
| POST | `/task/storage/workflow/execute/{id}` | 执行流程 |

## 5. 智能、开发与公共功能

### 5.1 AI 聊天与模型配置

**业务目标**：提供用户聊天会话，以及可切换的个人模型配置。

**主要数据**：会话和消息由 Agno 会话存储管理；用户模型配置存于 Redis。会话按当前用户读取和修改。模型配置包括名称、模型、服务地址及访问凭据等参数。

**业务规则**：用户只能管理自己的会话，可创建、分页查询、查看、改名和删除。HTTP 接口返回完整的非流式回答及会话 ID；WebSocket 用于实时对话。对话优先使用用户已激活的模型配置；模型配置可新增、更新、删除和激活。实际回复依赖已配置的模型服务。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET / POST / PUT / DELETE | `/ai/chat/list`、`/ai/chat/detail/{session_id}`、`/ai/chat/create`、`/ai/chat/update/{session_id}`、`/ai/chat/delete` | 会话维护 |
| POST / WS | `/ai/chat/ai-chat`、`/ai/chat/ws` | 非流式及 WebSocket 对话 |
| GET / POST / PUT / DELETE | `/ai/chat/model`、`/ai/chat/model/{config_id}`、`/ai/chat/model/{config_id}/activate` | 模型配置管理与激活 |

### 5.2 代码生成

**业务目标**：从数据库表生成管理功能代码，并维护生成配置。

**数据模型**：`gen_table` 保存表名、类名、生成包/模块/业务名、生成路径及主子表配置；`gen_table_column` 保存字段名、类型、显示、查询和表单配置。

**业务规则**：从现有数据库导入表和列后可编辑生成参数；可预览代码、输出单表代码或批量下载；同步数据库前可获取差异预览。创建表结构接口接收 SQL，并由代码生成服务执行校验和落库。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/generator/gencode/list`、`/generator/gencode/db/list`、`/generator/gencode/detail/{table_id}` | 生成配置与数据库表查询 |
| POST / PUT / DELETE | `/generator/gencode/import`、`/generator/gencode/create`、`/generator/gencode/update/{table_id}`、`/generator/gencode/delete` | 导入、建表和编辑配置 |
| GET | `/generator/gencode/preview/{table_id}`、`/generator/gencode/sync_db/preview/{table_name}` | 代码预览与数据库差异预览 |
| POST / PATCH | `/generator/gencode/output/{table_name}`、`/generator/gencode/batch/output`、`/generator/gencode/sync_db/{table_name}` | 单表输出、批量下载与数据库同步 |

### 5.3 公共文件与示例扩展

**公共文件**：`/common/file/upload` 上传文件并返回文件名、映射路径和访问地址；`/common/file/download` 下载受控文件。两者分别需要上传和下载权限。

**示例扩展**：启动时动态发现 `app/plugin/module_*/**/controller.py` 中的路由。仓库内 `module_example/demo` 提供示例记录的详情、分页、增删改、启停、Excel 导入导出和模板下载，用于验证插件开发约定。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET / POST / PUT / DELETE / PATCH | `/example/demo/list`、`/example/demo/detail/{id}`、`/example/demo/create`、`/example/demo/update/{id}`、`/example/demo/delete`、`/example/demo/status/batch` | 示例数据管理 |
| POST | `/example/demo/export`、`/example/demo/import`、`/example/demo/download/template` | 示例数据 Excel 处理 |

## 6. 监控与运维

### 6.1 健康检查和服务器状态

健康检查执行数据库 `SELECT 1` 与 Redis `PING`，返回服务名、版本、环境及连接状态；SSE 提供持续状态流。服务器信息接口返回 CPU、内存、磁盘、系统和 Python 运行信息。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/monitor/health/check`、`/monitor/health/stream` | 单次健康检查、健康状态 SSE |
| GET | `/monitor/server/info` | 服务器资源信息 |

### 6.2 在线会话、缓存和统计

在线会话从 Redis 的会话令牌读取，可按名称、IP、登录地点过滤；可查询本人会话、强制下线指定会话或清空在线会话。缓存监控可查看 Redis 信息、缓存名称、键和值，并清理指定缓存或所有缓存。基础统计提供在线人数、用户数、近期登录等指标。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/monitor/online/list`、`/monitor/online/current`、`/monitor/online/stats` | 在线会话与基础统计 |
| DELETE | `/monitor/online/delete`、`/monitor/online/clear` | 强制下线与清空会话 |
| GET | `/monitor/cache/info`、`/monitor/cache/get/names`、`/monitor/cache/get/keys/{cache_name}`、`/monitor/cache/get/value/{cache_name}/{cache_key}` | 缓存查询 |
| DELETE | `/monitor/cache/delete/name/{cache_name}`、`/monitor/cache/delete/key/{cache_key}`、`/monitor/cache/clear` | 缓存清理 |

## 7. 数据对象索引

| 领域 | 持久化对象 | 关系或用途 |
| --- | --- | --- |
| 账号与组织 | `sys_user`、`sys_role`、`sys_menu`、`sys_dept`、`sys_position` | 用户关联角色、岗位和部门；角色关联菜单。 |
| 配置与内容 | `sys_dict_type`、`sys_dict_data`、`sys_param`、`sys_notice`、`sys_version` | 字典、参数、公告和版本内容。 |
| 服务台与审计 | `sys_ticket`、`sys_ticket_comment`、`sys_login_log`、`sys_operation_log` | 工单、评论、登录及操作记录。 |
| 计划任务 | `task_cornjob_node`、`task_corn_job` | 任务定义与执行日志。 |
| 存储与传输 | `task_storage_node`、`task_storage_transfer`、`task_storage_transfer_step`、`task_storage_workflow`、`task_storage_workflow_node`、`task_storage_workflow_edge` | 存储连接、传输任务/步骤及可重复执行的流程。 |
| 开发扩展 | `gen_table`、`gen_table_column`、`example_demo` | 代码生成配置与示例插件数据。 |
| 非关系型状态 | Redis 会话、验证码、参数/字典缓存、AI 用户模型配置；Agno 聊天会话表 | 认证、缓存和聊天状态。 |

通用业务表采用软删除与审计字段。涉及用户、角色、部门等关联对象时，删除或停用后的影响以对应 Service 的校验和查询过滤规则为准。

## 8. 核对来源

- 需求背景：仓库根目录 `REQUIREMENTS.md`。
- 实际路由：`backend/app/api/v1/routers.py`、各模块 `controller.py`、`backend/app/core/discover.py`。
- 实际字段和业务规则：各模块 `model.py`、`schema.py`、`service.py`。
- 通用契约：`backend/app/core/base_schema.py`、`backend/app/core/base_crud.py`、`backend/app/core/permission.py`、`backend/app/core/dependencies.py`。
