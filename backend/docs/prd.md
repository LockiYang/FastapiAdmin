# FastapiAdmin 产品需求文档

| 项 | 说明 |
| --- | --- |
| 产品 | FastapiAdmin 管理后台 |
| 版本 | v3.0.0 |
| 技术栈 | 后端 Python + FastAPI + SQLAlchemy + Redis；管理端 Vue 3 + Element Plus + TypeScript + Vite + Pinia；移动端 uni-app |
| 应用划分 | 管理端 `frontend/web`、移动端 `frontend/app`、后端 `backend` |
| 文档范围 | 本仓库已实现的后端能力 |

## 1. 产品概述

FastapiAdmin 是一套前后端分离的管理后台。它提供一套账号体系、菜单与按钮权限、部门数据范围、字典与系统参数、公告、工单、版本、审计日志，以及定时任务、多协议存储与文件传输、AI 对话和代码生成。

产品同时服务管理端和移动端，两端共用同一套账号与令牌。菜单用 `scope` 区分可见端：`web` 为管理端，`desktop` 与 `app` 为移动端。

使用者：

- **超级管理员**：`sys_user.is_superuser = true`。跳过功能权限和数据范围检查，管理全平台账号与运行资源。
- **后台管理员**：按已授权菜单和按钮工作，数据可见范围由角色的 `data_scope` 决定。
- **普通用户**：登录、维护个人资料、查看获授权的数据并使用业务功能。
- **访客**：使用登录、验证码、注册和已发布版本查询等开放接口。

## 2. 全局约定

### 2.1 业务描述

所有 JSON 接口共用同一套响应、鉴权和列表查询约定。受保护接口默认要求登录，并按菜单上的 `permission` 标识鉴权。文件下载、SSE 和 WebSocket 使用各自的协议，不套这层 JSON 信封。

### 2.2 业务规则

- 统一响应：`{ code, msg, data, status_code, success }`。`code == 0` 表示成功。`status_code` 与 HTTP 状态一致。
- 未登录或令牌无效时，业务码使用 `401`（未授权）、`10401`（认证过期，需重新登录）、`4504`（无效令牌）或 `4505`（令牌过期），以前端约定的认证码为准。
- 已登录但没有对应权限标识时返回 `10403`（无权限操作）。
- 访问令牌放在请求头 `Authorization: Bearer <access_token>`。登录成功同时签发刷新令牌。JWT 的 `sub` 是会话 ID，不是用户 ID。
- 访问令牌和刷新令牌默认各有效 12 小时（`ACCESS_TOKEN_EXPIRE_SECONDS` / `REFRESH_TOKEN_EXPIRE_SECONDS`）。
- 请求认证同时校验令牌签名、Redis 中的会话，以及数据库里的用户状态。停用账号不能继续使用旧会话。
- 刷新接口轮换刷新令牌。已经失效的旧刷新令牌再次使用时，撤销该会话。
- 退出登录删除该会话在 Redis 中的访问令牌、刷新令牌和会话信息。
- 账号密码登录对非本地 IP 做 Redis 固定窗口限流。滑块验证码默认开启（`CAPTCHA_ENABLE`），有效期 60 秒。
- 新密码长度 6–128，且须同时覆盖字母、数字、符号中的至少两类。修改密码时，旧密码只校验长度。密码以哈希存储，接口不回显。
- 演示模式（参数 `demo_enable`）下，非 GET 且不在白名单路径、来源 IP 也不在 `ip_white_list` 的请求被拒绝。`ip_black_list` 中的 IP 直接拒绝。
- 通用状态：`0` 启用，`1` 停用。公告、工单、版本、传输任务、登录日志另有自己的状态，以对应模块为准。
- 删除为软删除：写入 `is_deleted` 与 `deleted_time`。列表默认不返回已删除行。
- 时间字段为带时区的日期时间，JSON 输出为统一的展示格式。

**通用字段**

业务表默认带 `ModelMixin`。带创建人审计的表再叠加 `UserMixin`。下文各表只列业务字段，并注明是否含用户审计。

| 字段 | 说明 |
| --- | --- |
| id | 主键 |
| uuid | 全局唯一标识 |
| is_deleted | 是否已删除 |
| created_time / updated_time / deleted_time | 创建、更新、删除时间 |
| created_id / updated_id / deleted_id | 仅 `UserMixin`。创建人、更新人、删除人，外键到 `sys_user`，删除用户时置空 |

**数据范围**

超管不套数据范围。其他用户只采用未删除且启用（`status = 0`）角色上的 `data_scope`。多角色并存时，`3` 优先，其次 `2`，否则按本人。

| 取值 | 生效含义 |
| --- | --- |
| `1` | 仅本人。用户表按用户 `id`；其他带 `created_id` 的表按创建人 |
| `2` | 当前用户所属部门及其子部门。用户表按用户自身 `dept_id`；其他表按创建人的 `dept_id`。子部门计算失败时降级为仅本部门 |
| `3` | 全部数据 |

读取、分页、统计，以及普通单条更新前的对象预读取，使用上述条件。没有 `created_id` 的模型不做这层过滤。通用批量写入 `set`、`delete` 不自行附加数据范围，由各业务在删除前做存在性和授权检查。

数据范围只有这三档。授权接口只接受 `1`–`3`。保存授权时清空 `sys_role_depts`，过滤不读取该表。

### 2.3 通用列表查询

分页接口接受：

| 参数 | 说明 |
| --- | --- |
| `page_no` | 页码，默认 1 |
| `page_size` | 每页条数，默认 10，最大 100 |
| `order_by` | JSON 数组，如 `[{"id":"asc"}]`。缺省按 `id` 升序 |
| `created_time` / `updated_time` | 可选的时间范围，传 `["start","end"]`，按区间过滤 |
| `created_id` / `updated_id` | 可选，按创建人、更新人精确匹配 |

各资源另有自己的筛选字段（名称、状态、类型等），随该资源的查询模型。成功时 `data` 为：

| 字段 | 说明 |
| --- | --- |
| `page_no` / `page_size` | 当前页与页大小 |
| `total` | 总条数 |
| `has_next` | 是否有下一页 |
| `items` | 当前页数据 |

树形资源（部门、菜单）返回树，不走上述分页信封。

### 2.4 通用 CRUD

多数资源遵循同一组动作。路径前缀在各模块给出，例如用户为 `/system/user`。下文只列出相对这张表的差异和该模块特有接口。对外访问通常再加 `/api/v1`。

| 方法 | 动作 | 说明 |
| --- | --- | --- |
| GET | `list` 或 `page` | 分页列表 |
| GET | `detail/{id}` | 单条 |
| POST | `create` | 新增。创建人、更新人取当前用户 |
| PUT | `update/{id}` | 保存单条 |
| DELETE | `delete` | 批量软删除，请求体为 ID 列表 |
| PATCH | `status/batch` | 批量启停，请求体为 `ids` 与 `status` |

部分资源使用 `tree` 代替 `list`，或没有启停、导出。以该模块的接口表为准。

### 2.5 鉴权头与入口

| 端 | 前缀 | 身份 |
| --- | --- | --- |
| 全部 JSON API | `/api/v1` | `Authorization: Bearer` |
| 开放接口 | 同上 | 登录、验证码、注册、已发布版本等不要求令牌 |

当前用户信息接口返回该用户可见的菜单树。管理端读取 `scope=web` 的菜单。权限标识形如 `module_system:user:query`，挂在菜单或按钮节点上。角色只收集「启用角色下的启用菜单」。

---

## 3. 登录与会话

### 3.1 业务描述

用户用账号密码进入系统，也可以走 GitHub、Gitee、QQ、微信开放平台或微信小程序。登录成功后签发一对令牌，并在 Redis 记下会话。会话里包含用户、权限标识、菜单 ID、登录 IP 和客户端信息。

### 3.2 业务规则

- 账号密码登录检查用户是否存在、密码是否正确、账号是否停用。
- 开启滑块验证码时，获取验证码、完成滑块、提交登录共用同一条验证码状态。
- 成功登录写入最后登录时间，并记一条成功登录日志（IP、地点、操作系统、浏览器）。失败记失败日志。
- 地点是否解析由参数 `ip_location_enable` 决定。
- OAuth 与小程序登录依赖部署时配置的应用凭据。小程序支持 code 登录、手机号登录，以及生成小程序码。
- 注册创建一个启用的普通账号，创建人与更新人记为该用户自身。
- 忘记密码只接收用户名并登记申请，不在该接口修改密码。

### 3.3 数据模型

不单独建登录表。账号见「用户」。登录结果见「日志」。令牌与验证码状态在 Redis：`access_token`、`refresh_token`、`user_session`、`captcha_codes`。

### 3.4 API 接口

| 方法 | 路径 | 登录 | 说明 |
| --- | --- | --- | --- |
| POST | `/system/auth/login` | 否 | 账号密码登录。成功返回访问令牌、刷新令牌、`token_type=Bearer`、`expires_in` |
| POST | `/system/auth/token/refresh` | 否 | 用刷新令牌轮换一对新令牌 |
| POST | `/system/auth/logout` | 是 | 注销当前会话 |
| GET / POST | `/system/auth/captcha/get`、`/system/auth/captcha/slider/complete` | 否 | 获取并完成滑块验证码 |
| GET | `/system/auth/oauth/{provider}/login` | 否 | 跳转第三方授权。`provider` 为 github、gitee、qq、wechat |
| GET | `/system/auth/oauth/{provider}/callback` | 否 | 第三方回调 |
| POST | `/system/auth/wx-login` | 否 | 微信小程序 code 登录 |
| POST | `/system/auth/wx-phone-login` | 否 | 微信小程序手机号登录 |
| POST | `/system/auth/wx-qrcode/generate` | 是 | 生成小程序码 |

---

## 4. 账号与组织

账号通过部门归属组织，通过角色获得菜单和数据范围，通过岗位做职务标记。一个用户最多一个部门，可以有多个角色和多个岗位。

### 4.1 用户

#### 业务描述

维护可登录的账号，指定部门、角色和岗位，并提供个人资料、改密、导入导出。

#### 业务规则

- 用户名全局唯一。管理端创建：字母开头，2–32 位，仅字母、数字、下划线和 `._-`。注册接口最少 3 位，规则同上。
- 昵称必填。手机号 11 位且符合号段；邮箱填写时须为合法邮箱。性别：`0` 男，`1` 女，`2` 未知。
- 分配角色或岗位时，目标必须存在且启用。
- 当前用户可改自己的基本资料，并用旧密码修改新密码。管理员重置他人密码时，不能重置超级管理员。
- 不能删除超级管理员，也不能删除当前登录用户。删除前先解除角色、岗位关系，再软删除。
- 列表与导出走数据范围。导入按行返回失败原因，并提供模板下载。
- 编辑用户时，提交空角色列表会清空角色；不传该字段或传 `null` 则保持原角色。岗位同理。

#### 数据模型

**sys_user 用户表**（含用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| username | varchar(64) unique | 登录账号 |
| password | varchar(255) | 密码哈希 |
| name | varchar(32) | 昵称 |
| mobile | varchar(11) | 手机号，可空 |
| email | varchar(64) | 邮箱，可空 |
| gender | varchar(1) | `0` 男，`1` 女，`2` 未知 |
| avatar | varchar(255) | 头像地址 |
| is_superuser | boolean | 是否超级管理员 |
| last_login | datetime | 最后登录时间 |
| dept_id | int | 部门 ID，可空 |
| status | int | `0` 启用，`1` 停用 |
| description | text | 备注 |
| github_login / gitee_login / wx_login / qq_login | varchar(32) | 第三方账号标识，可空 |

**sys_user_roles**：`user_id` + `role_id`。**sys_user_positions**：`user_id` + `position_id`。均为联合主键，删除用户或角色时级联删除关联。

#### API 接口

前缀 `/system/user`。列表、详情、新增、修改、删除、批量启停使用通用 CRUD。

| 差异 | 说明 |
| --- | --- |
| GET `current/info` | 当前用户资料与可见菜单。`check_data_scope=false` 时只返回菜单和权限 |
| PUT `current/info/update` | 修改本人资料 |
| PUT `password/change` | 本人修改密码，需旧密码 |
| PUT `password/reset/{id}` | 管理员重置他人密码 |
| POST `password/forget` | 忘记密码申请，不改密码 |
| POST `register` | 开放注册 |
| GET `import/template` | 下载导入模板 |
| POST `import/data` | 导入用户 |
| POST `export` | 按当前查询条件导出 Excel |

### 4.2 角色

#### 业务描述

角色把一组菜单权限和一个数据范围交给用户。用户的功能权限是其全部启用角色的并集。

#### 业务规则

- 名称必填。编码全局唯一：字母开头，2–64 位，仅字母、数字、下划线。
- `data_scope` 只取 `1`、`2`、`3`，含义见全局约定。默认 `1`。
- 授权接口一次提交角色 ID 列表、菜单 ID 列表和 `data_scope`，整体替换这些角色的菜单，并写入数据范围。角色和菜单都必须存在。
- 仍关联未删除用户的角色不能删除，须先解除用户关联。停用用户也算有效关联。批量删除时任一角色不满足则整批拒绝。
- 可以批量启停，并导出 Excel。选项接口只返回可用角色。

#### 数据模型

**sys_role 角色表**（含用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| name | varchar(64) | 角色名称 |
| code | varchar(64) unique | 角色编码 |
| order | int | 显示排序，默认 999 |
| status | int | `0` 启用，`1` 停用 |
| data_scope | int | `1` 仅本人，`2` 本部门及以下，`3` 全部。默认 1 |
| description | text | 备注 |

**sys_role_menus**：`role_id` + `menu_id`。

**sys_role_depts**：`role_id` + `dept_id`。保存授权时清空，不参与数据范围。

#### API 接口

前缀 `/system/role`。列表、详情、新增、修改、删除、批量启停使用通用 CRUD。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/system/role/options` | 可用角色下拉 |
| PUT | `/system/role/permission` | 替换菜单并保存数据范围。权限标识 `module_system:role:permission` |
| POST | `/system/role/export` | 导出角色 |

### 4.3 菜单

#### 业务描述

目录、菜单、按钮和外链都是权限节点。管理端用菜单节点注册路由，用按钮节点上的 `permission` 控制接口和页面操作。

#### 业务规则

- 类型 `type`：`1` 目录，`2` 菜单，`3` 按钮，`4` 外链。
- 目录下可以放目录、菜单或外链。菜单下可以放按钮。子节点的可见范围与父节点一致。
- `permission` 是鉴权键。`route_name`、`route_path`、`component_path` 给前端注册路由。`link` 仅外链使用。`is_iframe` 表示内嵌打开。
- `keep_alive` 为真时标签页缓存该页面。`hidden` 为真时不出现在菜单。`affix` 固定标签。`scope` 为 `web`、`desktop` 或 `app`。
- `status = 1` 的节点不参与菜单展示，也不参与鉴权。
- 删除菜单时连同后代一起处理。批量启用时联动祖先；批量停用时联动子孙。
- `order` 越小越靠前（默认 999）。

#### 数据模型

**sys_menu 菜单表**（无用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| name | varchar(64) | 菜单名称 |
| type | int | `1` 目录，`2` 菜单，`3` 按钮，`4` 外链 |
| order | int | 排序 |
| permission | varchar(100) | 权限标识 |
| icon | varchar(50) | 图标 |
| route_name | varchar(100) | 路由名称 |
| route_path | varchar(200) | 路由路径 |
| component_path | varchar(200) | 前端组件路径 |
| redirect | varchar(200) | 重定向 |
| hidden | boolean | 是否隐藏 |
| keep_alive | boolean | 是否缓存，默认是 |
| always_show | boolean | 是否始终显示 |
| title | varchar(50) | 标题 |
| params | json | 路由参数 |
| affix | boolean | 是否固定标签 |
| link | varchar(500) | 外链地址 |
| is_iframe | boolean | 是否 iframe |
| is_hide_tab | boolean | 是否隐藏标签页 |
| active_path | varchar(200) | 高亮用的上级路径 |
| show_badge | boolean | 是否显示红点 |
| show_text_badge | varchar(20) | 文字角标 |
| scope | varchar(20) | `web` / `desktop` / `app`，默认 `web` |
| status | int | `0` 启用，`1` 停用 |
| description | text | 备注 |
| parent_id | int | 父节点，空为顶级 |

#### API 接口

前缀 `/system/menu`。没有分页列表，用树代替。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/system/menu/tree` | 菜单树 |
| GET | `/system/menu/detail/{id}` | 详情 |
| POST / PUT / DELETE / PATCH | `create`、`update/{id}`、`delete`、`status/batch` | 通用维护。删除含后代；启停联动父子 |

### 4.4 部门

#### 业务描述

部门是树形组织。用户的部门数据范围沿这棵树向下展开。

#### 业务规则

- 名称必填。编码全局唯一，规则同角色编码。
- 存在子部门时不能删除父部门。
- 批量启用时联动上级，批量停用时联动下级。
- `parent_id` 为空表示顶级。

#### 数据模型

**sys_dept 部门表**（含用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| name | varchar(64) | 部门名称 |
| code | varchar(64) unique | 部门编码 |
| parent_id | int | 上级部门 |
| order | int | 排序，默认 999 |
| status | int | `0` 启用，`1` 停用 |
| description | text | 备注 |

#### API 接口

前缀 `/system/dept`。用 `tree` 代替分页列表，其余为详情、新增、修改、删除、批量启停。

### 4.5 岗位

#### 业务描述

岗位是独立于部门树的职务目录，只用于给用户打标，不参与数据范围。

#### 业务规则

- 名称必填。编码全局唯一，规则同角色编码。
- 可按状态取下拉选项，并导出 Excel。

#### 数据模型

**sys_position 岗位表**（含用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| name | varchar(64) | 岗位名称 |
| code | varchar(64) unique | 岗位编码 |
| order | int | 排序，默认 1 |
| status | int | `0` 启用，`1` 停用 |
| description | text | 备注 |

#### API 接口

前缀 `/system/position`。列表、详情、新增、修改、删除、批量启停使用通用 CRUD。另有 `GET options` 与 `POST export`。

---

## 5. 配置与内容

### 5.1 字典

#### 业务描述

字典为页面上的下拉、标签和状态色提供选项。类型和条目分开维护，启动时写入 Redis，按类型编码读取。

#### 业务规则

- 类型编码 `dict_type` 全局唯一。
- 条目通过 `dict_type_id` 归属类型，同时冗余 `dict_type` 编码供查询。
- 条目可标记默认项，并用 `list_class`、`css_class` 控制表格展示。
- 类型与条目都可批量启停。

#### 数据模型

**sys_dict_type**（无用户审计）：`dict_name`、唯一 `dict_type`、`status`、`description`。

**sys_dict_data**（无用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| dict_type_id | int | 所属类型，删除类型时级联 |
| dict_type | varchar(255) | 类型编码冗余 |
| dict_label | varchar(255) | 显示标签 |
| dict_value | varchar(255) | 存储值 |
| dict_sort | int | 排序 |
| is_default | boolean | 是否默认 |
| css_class / list_class | varchar(255) | 样式与表格回显 |
| status | int | `0` 启用，`1` 停用 |
| description | text | 备注 |

#### API 接口

类型前缀 `/system/dict/type`，条目前缀 `/system/dict/data`。两边都使用通用 CRUD（含批量启停）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/system/dict/type/optionselect` | 类型下拉 |
| GET | `/system/dict/data/info/{dict_type}` | 按类型编码读取条目 |

### 5.2 系统参数

#### 业务描述

用键值保存站点名称、登录页文案、备案、隐私条款和访问控制开关。修改后同步 Redis，读取走缓存。

#### 业务规则

- 修改时不允许改 `config_key`。
- `config_type = true` 表示系统内置项。
- `demo_enable`、`ip_white_list`、`ip_black_list` 由请求中间件读取，规则见全局约定。

内置键：

| config_key | 说明 |
| --- | --- |
| sys_name / version | 站点名称、对外版本号 |
| logo_url / favicon / login_bg | 标志、图标、登录背景 |
| login_title / login_subtitle | 登录页标题与副标题 |
| copyright / keep_record | 版权、备案号 |
| help_doc / git_code | 帮助文档、仓库地址 |
| privacy / clause | 隐私政策、用户条款 |
| demo_enable | 演示模式，禁止非白名单写操作 |
| ip_white_list / ip_black_list | IP 白名单、黑名单 |
| ip_location_enable | 是否解析登录地点 |

#### 数据模型

**sys_param**（无用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| config_name | varchar(64) | 参数名称 |
| config_key | varchar(500) | 参数键 |
| config_value | text | 参数值 |
| config_type | boolean | 是否内置 |
| status | int | `0` 启用，`1` 停用 |
| description | text | 备注 |

本模块不提供通用新增和删除接口。

#### API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/system/param/info` | 从缓存读取参数 |
| PUT | `/system/param/update/{id}` | 修改参数值并刷新缓存 |

### 5.3 公告

#### 业务描述

发布通知和公告。创建、修改、启停后通过 SSE 通知在线客户端刷新列表。

#### 业务规则

- 标题不能为空，且不能与已有标题重复。内容做 HTML 清理。
- 类型：`1` 通知，`2` 公告。
- 状态：`0` 草稿，`1` 已发布，`2` 已归档。这组状态不沿用通用启停语义。
- 变更时广播 `notice_update`，载荷是轻量事件，客户端自行重新拉取列表。
- `available` 按 `status = 0` 返回最多 10 条。

#### 数据模型

**sys_notice**（含用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| notice_title | varchar(64) | 标题 |
| notice_type | varchar(1) | `1` 通知，`2` 公告 |
| notice_content | text | 正文 |
| status | int | `0` 草稿，`1` 已发布，`2` 已归档 |
| description | text | 备注 |

#### API 接口

前缀 `/system/notice`。列表、详情、新增、修改、删除、批量改状态使用通用 CRUD。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/system/notice/available` | 返回 `status = 0` 的公告，最多 10 条 |
| GET | `/system/notice/stream` | 公告变更 SSE |

### 5.4 版本

#### 业务描述

记录产品版本说明，并可标记该版本是否要求用户重新登录。

#### 业务规则

- 版本号唯一。
- 状态：`0` 草稿，`1` 已发布，`2` 已回滚。
- 已发布列表只返回 `status = 1`。
- `require_re_login` 为真时，客户端应结束当前会话。

#### 数据模型

**sys_version**（含用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| version | varchar(32) unique | 版本号 |
| title | varchar(200) | 标题 |
| date | varchar(50) | 发布日期 |
| content | text | 富文本说明 |
| sort | int | 排序 |
| status | int | `0` 草稿，`1` 已发布，`2` 已回滚 |
| require_re_login | boolean | 是否要求重新登录 |
| description | varchar(500) | 备注 |

#### API 接口

前缀 `/system/versions`。列表、详情、新增、修改、删除使用通用 CRUD。没有批量启停，状态走单独接口。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/system/versions/published` | 已发布版本。开放查询 |
| PUT | `/system/versions/{id}/status` | 修改状态 |

---

## 6. 工单

### 6.1 业务描述

用户提交建议、缺陷、优化或其他反馈。管理员指派处理人、回复、流转状态，参与人可以评论。

### 6.2 业务规则

- 标题必填。类型：`suggestion` 建议，`bug` 缺陷，`optimize` 优化，`other` 其他。默认建议。
- 正文为富文本，`summary` 存纯文本摘要，`images` 存图片 URL 的 JSON 数组。
- 状态：`0` 待处理，`1` 处理中，`2` 已完成，`3` 已关闭。

| 原状态 | 目标状态 | 可操作人 |
| --- | --- | --- |
| 待处理 | 处理中 | 创建人、处理人、超级管理员 |
| 待处理 | 已关闭 | 创建人、超级管理员 |
| 处理中 | 已完成 | 处理人、超级管理员 |
| 处理中 | 已关闭 | 创建人、处理人、超级管理员 |
| 已完成 | 已关闭 | 创建人、超级管理员 |
| 已关闭 | 待处理 | 超级管理员 |

- 更改处理人时，目标用户必须可被当前操作者查询到。
- 批量更新逐条校验状态流转，一条不合法则该条失败。
- 统计分别计数待处理、处理中、已完成。
- 评论前工单必须存在。

### 6.3 数据模型

**sys_ticket**（含用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| title | varchar(200) | 标题 |
| ticket_type | varchar(20) | 类型 |
| ticket_content | text | 富文本正文 |
| summary | text | 纯文本摘要 |
| images | text | 图片 URL JSON |
| reply | text | 处理回复 |
| assigned_id | int | 处理人 |
| status | int | `0`–`3`，见上表 |
| description | text | 备注 |

**sys_ticket_comment**（含用户审计）：`ticket_id`、`content`。删除工单时级联删除评论。

### 6.4 API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/system/ticket/stats` | 待处理、处理中、已完成计数 |
| GET | `/system/ticket/list`、`/system/ticket/detail/{id}` | 分页与详情 |
| POST / PUT / DELETE | `/system/ticket/create`、`update/{id}`、`delete` | 新增、修改、删除 |
| PUT | `/system/ticket/batch` | 批量流转状态 |
| POST | `/system/ticket/export` | 导出 |
| GET / POST | `/system/ticket/{ticket_id}/comments` | 评论分页与新增 |

---

## 7. 日志

### 7.1 业务描述

登录日志记录每次登录成败。操作日志记录后台写操作的请求与响应，供审计检索和导出。

### 7.2 业务规则

- 登录状态：`1` 成功，`2` 失败。与通用启停的 `0/1` 不同。
- 操作状态：`0` 成功，`1` 失败。
- 操作日志保存路径、方法、请求体、响应体、耗时、IP 和操作人用户名。大文本列随数据库选择（MySQL 用 LONGTEXT）。
- 两类日志都可以查询和删除。操作日志可以导出。日志表没有用户审计字段，操作人用 `username` 快照。

### 7.3 数据模型

**sys_login_log**（无用户审计）：`username`、`status`、`login_ip`、`login_location`、`request_os`、`request_browser`、`msg`、`description`。

**sys_operation_log**（无用户审计）：`username`、`status`、`request_path`、`request_method`、`request_payload`、`response_code`、`response_json`、`process_time`、`request_ip`、`description`。

### 7.4 API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET / DELETE | `/system/log/login/list`、`detail/{id}`、`delete` | 登录日志查询与删除 |
| GET / DELETE / POST | `/system/log/operation/list`、`detail/{id}`、`delete`、`export` | 操作日志查询、删除与导出 |

---

## 8. 定时任务

### 8.1 业务描述

管理员维护可按计划或手动运行的任务节点，查看执行日志，并对调度器做启停。节点描述「做什么、何时做」；执行日志描述「某一次跑得怎样」。

### 8.2 业务规则

- 节点编码唯一。`func` 为处理函数：可以是 `builtin:` 内置处理器，也可以是代码块。代码块能否执行由 `SCHEDULER_ALLOW_CODE_EXEC` 决定。
- 触发器：`cron`、`interval`、`date`。填写了触发器就必须填写触发参数。留空则只保存节点，通过手动执行接口运行。
- `coalesce` 合并错过的执行。`max_instances` 限制并发实例，默认 1。
- 节点状态沿用 `0` 启用、`1` 停用。
- 执行状态：`0` 待执行，`1` 执行中，`2` 成功，`3` 失败，`4` 超时，`5` 取消。
- 列表可以带出下一次运行时间、最近一次运行时间，以及当前不能调度的原因。
- 调度器可以启动、暂停、恢复、关闭、清空任务和查看控制台。单个任务可以暂停、恢复、立即运行、修改触发参数、移除。

### 8.3 数据模型

**task_cornjob_node 任务节点**（含用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| name | varchar(64) | 名称 |
| code | varchar(32) unique | 编码 |
| func | text | 处理函数或代码块 |
| args / kwargs | text | 位置参数、关键字参数 |
| trigger | varchar(64) | `cron` / `interval` / `date`，可空 |
| trigger_args | text | 触发参数 |
| jobstore | varchar(64) | 任务存储，默认 `default` |
| executor | varchar(64) | 执行器，默认 `threadpool` |
| coalesce | boolean | 是否合并执行 |
| max_instances | int | 最大并发实例 |
| start_date / end_date | varchar(64) | 生效区间 |
| status | int | `0` 启用，`1` 停用 |
| description | text | 备注 |

**task_corn_job 执行日志**（无用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| job_id | varchar(64) | 调度器中的任务 ID |
| job_name | varchar(128) | 任务名称 |
| trigger_type | varchar(32) | `cron` / `interval` / `date` / `manual` |
| next_run_time | varchar(64) | 下次执行时间 |
| job_state | text | 任务状态快照 |
| result / error | text | 结果与错误 |
| status | int | `0`–`5`，见上 |
| description | text | 备注 |

### 8.4 API 接口

节点前缀 `/task/cronjob/node`。列表、详情、新增、修改、删除、批量启停使用通用 CRUD。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/task/cronjob/node/options` | 节点下拉 |
| POST | `/task/cronjob/node/execute/{id}` | 手动执行 |
| POST | `/task/cronjob/node/clear` | 清空节点 |

调度器与执行日志：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/task/cronjob/job/scheduler/status` | 调度器状态 |
| GET | `/task/cronjob/job/scheduler/jobs` | 当前任务清单 |
| GET | `/task/cronjob/job/scheduler/console` | 控制台 |
| POST | `.../scheduler/start`、`pause`、`resume`、`shutdown` | 启停调度器 |
| DELETE | `.../scheduler/jobs/clear` | 清空调度任务 |
| POST / PUT / DELETE | `.../task/pause/{job_id}`、`resume`、`run`、`modify`、`remove` | 控制单个任务 |
| GET / DELETE | `/task/cronjob/job/log/list`、`detail/{id}`、`delete` | 执行日志 |

---

## 9. 存储与传输

### 9.1 存储源

#### 业务描述

用统一配置连接本地磁盘、FTP/FTPS/SFTP 和对象存储，供浏览、传输和流程复用。

#### 业务规则

- 协议：`local`、`ftp`、`ftps`、`sftp`、`s3`、`obs`、`oss`、`cos`。名称唯一。
- 创建和修改时按协议校验连接字段。对象存储需要桶；endpoint、region 等是否必填由该协议的校验决定。
- 密码和密钥加密保存，响应不回明文。
- 可用已保存的源或一份临时配置测试连接。
- 调用方未指定源时，先用默认且启用的源，否则用其他启用源。
- 同一时刻只应有一个默认源。状态 `0` 启用，`1` 停用。

#### 数据模型

**task_storage_node**（含用户审计）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| name | varchar(64) unique | 名称 |
| protocol | varchar(16) | 协议 |
| host / port | varchar / int | 主机与端口。对象存储可不填 host |
| username / password | varchar / text | 账号与加密后的密钥 |
| bucket / endpoint / region | varchar | 对象存储桶、接入点、区域 |
| path_prefix | varchar(255) | 路径前缀 |
| scheme | varchar(16) | 对象存储 `http` 或 `https`，默认 https |
| is_secure / implicit_tls / encrypt_type | | FTPS 的 TLS 方式。`encrypt_type`：`0` 明文，`1` 显式 TLS 可用时，`2` 要求显式 TLS，`3` 隐式 TLS |
| connection_mode | int | `0` 默认，`1` 主动，`2` 被动 |
| encoding | varchar(16) | 默认 UTF-8 |
| multipart_part_size | int | 分片大小，MB，默认 50 |
| multipart_concurrency | int | 分片并发，默认 6 |
| multipart_memory_budget | int | 分片内存预算，MB，默认 512 |
| advanced_config | json | 按协议解析的 SDK 高级项 |
| is_default | boolean | 是否默认源 |
| status | int | `0` 启用，`1` 停用 |
| description | text | 备注 |

#### API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/task/storage/node/protocols`、`advanced-fields` | 协议列表与高级字段定义 |
| GET | `page`、`list`、`detail/{id}` | 分页、简表、详情 |
| POST / PUT / DELETE | `create`、`update/{id}`、`delete` | 维护 |
| POST | `test`、`test/{id}` | 测试临时配置或已有源 |

### 9.2 文件浏览

#### 业务描述

在已启用的存储源上列目录、上传、下载、打包目录、删除、复制或移动、重命名、建目录和生成分享链接。

#### 业务规则

- 操作必须指定可用存储源和合法路径。
- 对象存储可以列桶。
- 目录下载打包为 ZIP。
- 连接失败或路径无效时拒绝操作，不部分提交。

#### 数据模型

不单独建表，读写目标存储源。

#### API 接口

前缀 `/task/storage/browse`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `list`、`buckets` | 文件列表、桶列表 |
| POST | `upload`、`download`、`download_dir` | 上传、下载文件、下载目录 ZIP |
| DELETE | `delete` | 删除 |
| POST | `copy`、`share` | 复制或移动、分享链接 |
| PUT | `rename`、`mkdir` | 重命名、创建目录 |

### 9.3 传输任务

#### 业务描述

把本地上传的文件或远端路径传到一个或多个目标存储源，并推送进度。

#### 业务规则

- 任务类型：`parallel` 每个目标都读原始源；`chain` 后一步读前一步的目标。
- 源类型：`remote` 指定源存储源和路径；`local` 先把文件收到服务端临时文件。
- 至少一个目标，且目标源存在并启用。源与目标不能是同一位置。
- 传输方式：`stream` 流式，`multipart` 分片。分片大小和并发可覆盖存储源默认值。留空则用存储源配置。
- 状态：`pending`、`running`、`success`、`failed`、`canceled`。
- 先落库任务和步骤，等请求事务提交后再启动后台传输。取消和删除受当前状态约束。
- SSE 推送进度，不替代列表查询。

#### 数据模型

**task_storage_transfer**（含用户审计）：`name`、`task_type`、`source_type`、`source_id`、`source_path`、`source_name`、`source_size`、`status`、`total_size`、`transferred_size`、`progress`（0–100）、`speed`（字节/秒）、`error_msg`、`started_at`、`finished_at`。

**task_storage_transfer_step**（无用户审计）：`task_id`、`step_order`（从 0）、`source_id`、`source_path`、`target_id`、`target_path`、`transfer_mode`、`multipart_part_size`、`multipart_concurrency`，以及与任务相同的状态、进度、速度、字节数和时间字段。删除任务时级联删除步骤。

#### API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/task/storage/transfer/task` | 创建远端源任务 |
| POST | `/task/storage/transfer/task/upload` | 上传本地文件并创建任务 |
| GET | `task/page`、`task/{id}` | 分页与详情（含步骤） |
| POST | `task/{id}/cancel` | 取消 |
| DELETE | `task` | 删除 |
| GET | `/task/storage/transfer/stream` | 进度 SSE |

### 9.4 传输流程

#### 业务描述

把存储源画成可重复执行的连线。执行时按启用的连线批量创建传输任务。

#### 业务规则

- 类型 `parallel` 或 `chain`，默认并行。
- `graph` 只存画布布局（位置、样式）。业务配置在节点表和连线表，回显时再组装，避免两份数据不一致。
- 节点绑定一个存储源和默认路径。连线的目标路径取目标节点的默认路径，连线本身不再写路径。
- 执行时只跑 `enabled = true` 的连线。没有启用连线、节点无效、源与目标相同或缺少路径时拒绝执行。
- 请求里可以覆盖源路径。成功时返回新建的传输任务 ID 列表。
- 流程状态 `0` 启用，`1` 停用。

#### 数据模型

**task_storage_workflow**（含用户审计）：`name`、`task_type`、`graph`、`status`、`description`。

**task_storage_workflow_node**（含用户审计）：`flow_id`、`node_key`、`source_id`、`source_path`。

**task_storage_workflow_edge**（含用户审计）：`flow_id`、`edge_key`、`source_node_key`、`target_node_key`、`enabled`、`transfer_mode`、`multipart_part_size`、`multipart_concurrency`。

#### API 接口

前缀 `/task/storage/workflow`。分页、简表、详情、新增、修改、删除使用通用 CRUD。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/task/storage/workflow/execute/{id}` | 按启用连线创建传输任务 |

---

## 10. AI 对话

### 10.1 业务描述

用户维护自己的聊天会话，并保存可切换的个人模型配置。回复来自用户已激活的模型服务。

### 10.2 业务规则

- 会话和消息按当前用户隔离。用户只能查看、改名和删除自己的会话。
- HTTP 对话返回完整的非流式回答和会话 ID。WebSocket 用于实时对话。
- 模型配置包括名称、模型、服务地址和访问凭据，存在 Redis，不落业务表。凭据属于该用户。
- 同一用户同时只有一个激活配置。未配置或上游不可用时，对话失败并返回错误，不伪造回复。

### 10.3 数据模型

会话与消息由 Agno 会话存储管理。模型配置键为 Redis `ai_model_config`。无本模块业务表。

### 10.4 API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET / POST / PUT / DELETE | `/ai/chat/list`、`create`、`detail/{session_id}`、`update/{session_id}`、`delete` | 会话 |
| POST | `/ai/chat/ai-chat` | 非流式对话 |
| WS | `/ai/chat/ws` | WebSocket 对话 |
| GET / POST / PUT / DELETE | `/ai/chat/model`、`/ai/chat/model/{config_id}` | 模型配置 |
| POST | `/ai/chat/model/{config_id}/activate` | 激活配置 |

---

## 11. 代码生成

### 11.1 业务描述

从当前数据库导入表，或提交建表 SQL，编辑字段在列表、表单、查询中的表现，然后预览并输出管理端代码。

### 11.2 业务规则

- 表名、实体类名、列名、列类型不能为空。
- 字段可标记主键、自增、可空、唯一，以及是否出现在新增、编辑、列表、查询中。
- `query_type` 决定查询方式，`html_type` 决定表单组件，`dict_type` 绑定字典。
- 支持主表关联子表（`sub_table_name`、`sub_table_fk_name`）和挂到指定父菜单（`parent_menu_id`）。
- 预览不写文件。单表输出写到生成路径；批量输出打包下载。
- 同步数据库前可以先看差异。创建表接口接收 SQL，由生成服务校验后落库。

### 11.3 数据模型

**gen_table**（含用户审计）：`table_name`、`table_comment`、`class_name`、`package_name`、`module_name`、`business_name`、`function_name`、`sub_table_name`、`sub_table_fk_name`、`parent_menu_id`、`status`、`description`。

**gen_table_column**（含用户审计）：`table_id`、`column_name`、`column_comment`、`column_type`、`column_length`、`column_default`、`is_pk`、`is_increment`、`is_nullable`、`is_unique`、`python_type`、`python_field`、`is_insert`、`is_edit`、`is_list`、`is_query`、`query_type`、`html_type`、`dict_type`、`sort`、`status`、`description`。删除表配置时级联删除列。

### 11.4 API 接口

前缀 `/generator/gencode`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `list`、`db/list`、`detail/{table_id}` | 已导入配置、库中的表、配置详情 |
| POST | `import`、`create` | 从库导入、执行建表 SQL |
| PUT / DELETE | `update/{table_id}`、`delete` | 修改配置、删除配置 |
| GET | `preview/{table_id}`、`sync_db/preview/{table_name}` | 代码预览、库差异预览 |
| POST | `output/{table_name}`、`batch/output` | 单表输出、批量下载 |
| PATCH | `sync_db/{table_name}` | 把配置同步到数据库 |

---

## 12. 监控与公共文件

### 12.1 业务描述

提供健康检查、本机资源、在线会话、Redis 缓存和基础统计，以及受权限控制的公共上传下载。

### 12.2 业务规则

- 健康检查执行数据库 `SELECT 1` 和 Redis `PING`，返回服务名、版本、环境和连接结果。
- 服务器信息包含 CPU、内存、磁盘、操作系统和 Python 运行信息。
- 在线会话来自 Redis。可按名称、IP、登录地点过滤，可查看本人会话、强制下线指定会话或清空在线会话。
- 缓存监控可查看 Redis 信息、缓存名、键和值，并清理指定缓存名、指定键或全部缓存。清理全部缓存需要独立权限。
- 基础统计包含在线人数、用户数和近期登录等指标。
- 公共上传返回文件名、映射路径和访问地址。下载按映射路径读取受控文件。上传、下载各自有权限标识。

### 12.3 数据模型

无独立业务表。在线会话结构见 Redis `user_session`：会话 ID、用户 ID、是否超管、用户状态、昵称、用户名、部门、手机、邮箱、性别、头像、权限标识、菜单 ID、IP、地点、操作系统、浏览器、登录时间、登录类型。

### 12.4 API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/monitor/health/check`、`/monitor/health/stream` | 单次健康检查、状态 SSE |
| GET | `/monitor/server/info` | 服务器资源 |
| GET | `/monitor/online/list`、`current`、`stats` | 在线会话、本人会话、基础统计 |
| DELETE | `/monitor/online/delete`、`clear` | 强制下线、清空会话 |
| GET | `/monitor/cache/info`、`get/names`、`get/keys/{cache_name}`、`get/value/{cache_name}/{cache_key}` | 缓存查询 |
| DELETE | `/monitor/cache/delete/name/{cache_name}`、`delete/key/{cache_key}`、`clear` | 缓存清理 |
| POST / GET | `/common/file/upload`、`/common/file/download` | 上传、下载 |

---

## 13. 示例插件

### 13.1 业务描述

仓库内的示例插件用来验证插件约定：启动时发现 `app/plugin/module_*/**/controller.py` 并注册路由。它不是独立业务。

### 13.2 业务规则

- 示例记录支持详情、分页、增删改、启停，以及 Excel 导入、导出和模板下载。
- 字段覆盖常用类型，便于对照代码生成和表单组件，不承载产品数据。

### 13.3 数据模型

**example_demo**（含用户审计）：`name`、`status`（`0` 正常，`1` 停用）、`description`，以及可空的 `int_val`、`bigint_val`、`float_val`、`bool_val`、`date_val`、`time_val`、`datetime_val`、`text_val`、`json_val`。

### 13.4 API 接口

前缀 `/example/demo`。列表、详情、新增、修改、删除、批量启停使用通用 CRUD。另有 `POST export`、`import`、`download/template`。

---

## 14. 模块关系

```text
用户 ──多对多── 角色 ──多对多── 菜单（permission = 鉴权键）
  │              │
  │              └── data_scope：1 本人 / 2 本部门及以下 / 3 全部
  ├── 属于一个部门（部门树决定范围 2）
  ├── 多对多岗位（不参与数据范围）
  ├── 产生登录日志、操作日志
  ├── 提交工单，并可被指派为处理人
  └── 拥有自己的 AI 会话与模型配置（Redis）

字典类型 ──一对多── 字典条目
系统参数 ──写入 Redis── 站点文案、演示模式、IP 黑白名单

任务节点 ──调度── 执行日志
存储源 ──被使用于── 文件浏览、传输步骤、流程节点
传输流程 ──执行时创建── 传输任务 ──展开为── 传输步骤

代码生成配置 ──一对多── 字段配置 ──输出── 管理端代码
示例插件 ──独立于── 上述业务，只验证插件加载
```

功能权限只来自菜单节点上的 `permission`。数据范围只来自角色的 `data_scope`，超管两种检查都跳过。文件传输的进度以任务和步骤表为准，SSE 只做推送。
