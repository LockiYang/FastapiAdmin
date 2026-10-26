# FastapiAdmin 产品需求文档

| 项 | 说明 |
| --- | --- |
| 产品 | FastapiAdmin 管理后台 |
| 版本 | v3.0.0 |
| 应用划分 | 管理端 `frontend/web`、移动端 `frontend/app`、后端 `backend` |
| 文档范围 | 本仓库已实现的后端能力 |

---

# Part 1：平台架构

---

## 1. 产品概述

FastapiAdmin 是一套前后端分离的应用管理系统，同时提供企业后台管理能力和前台用户基础服务。后台提供账号管理、菜单与按钮权限、部门数据范围、字典与系统参数、公告、工单、版本、审计日志，以及定时任务、多协议存储与文件传输和代码生成；前台支持用户注册、登录、维护个人资料及使用面向用户开放的业务功能。

使用者：

- **后台管理员**
  - 超级管理员负责系统配置、账号与权限管理及获授权的业务管理。超级管理员由 `sys_user.is_superuser = true` 标识，跳过功能权限和数据范围检查；
  - 普通管理员按已授权菜单和按钮工作，数据可见范围由角色的 `data_scope` 决定。
- **前台用户**：使用注册、登录、个人资料维护等基础服务，并在授权范围内使用前台业务功能。

## 2. 全局约定

### 2.1 适用范围

第 2.2–2.4 节描述当前后台管理员接口的响应、鉴权和通用数据约定，适用于超级管理员及其他管理员。前台用户单独建立响应与鉴权约定，不直接套用后台管理员的菜单、角色和部门数据范围规则，见第 2.5 节。

### 2.2 后台管理员响应、鉴权与数据规则

- **响应**：JSON 接口统一返回 `{ code, msg, data, status_code, success }`，`code = 0` 表示成功，`status_code` 与 HTTP 状态一致。文件下载、SSE 和 WebSocket 使用各自协议。
- **鉴权入口**：对外 API 前缀为 `/api/v1`，受保护接口使用 `Authorization: Bearer <access_token>`；登录、验证码等开放接口不要求访问令牌。具体入口以模块接口表为准。
- **会话**：登录签发访问令牌和刷新令牌，默认有效期各 12 小时，以配置为准；JWT 的 `sub` 为会话 ID。认证校验令牌、Redis 会话及账号状态；刷新轮换令牌，退出注销会话。登录、验证码和限流流程见第 3 节。
- **功能权限**：超管身份由 `sys_user.is_superuser = true` 决定，绕过角色权限和数据范围检查；其他管理员按有效角色授权。菜单和按钮的 `permission` 如 `module_system:user:query`，管理端菜单使用 `scope=web`；停用角色或菜单不参与授权。认证失效及无权限按现有认证错误码返回。
- **密码与访问限制**：密码以哈希存储、不回显；新密码长度 6–128，至少覆盖字母、数字、符号中的两类。演示模式限制写操作，IP 黑名单拒绝访问，具体取值由系统配置控制。
- **通用数据**：常规状态为 `0` 启用、`1` 停用，特殊业务状态以各模块为准；软删除设置 `is_deleted`、`deleted_time`，列表默认排除已删除数据。时间字段使用带时区日期时间，按统一格式输出。

**通用字段**

业务表使用 `ModelMixin`；需要后台操作人审计的表叠加 `UserMixin`。各模块的数据模型只列关联关系、身份授权、状态流转或业务执行所需的关键字段，不作为完整数据库字段字典；省略普通展示字段、备注、重复审计字段和 SQL 类型长度。关联说明区分数据库外键与业务引用，完整定义以 ORM 模型和 Schema 为准。

| 字段 | 说明 |
| --- | --- |
| `id` / `uuid` | 主键 / 全局唯一标识 |
| `is_deleted` | 软删除标记 |
| `created_time` / `updated_time` / `deleted_time` | 创建、更新、删除时间 |
| `created_id` / `updated_id` / `deleted_id` | 仅 `UserMixin`，关联 `sys_user` 的后台操作人，账号删除时置空；不表示前台用户归属 |

**数据范围**

除超管外，仅采用未删除且启用角色的 `data_scope`。多角色时 `3` 优先，其次 `2`，否则按本人；授权范围只接受以下三档。

| 取值 | 含义 |
| --- | --- |
| `1` | 仅本人：用户表按用户 ID，其他带 `created_id` 的表按创建人 |
| `2` | 所属部门及子部门：用户表按自身部门，其他表按创建人的部门；子部门计算失败时降级为本部门 |
| `3` | 全部数据 |

上述范围用于读取、分页、统计和普通单条更新前的对象查询。没有 `created_id` 的模型不做这层过滤；通用批量写入不会自动附加范围，业务层须检查授权。部门数据范围不作为前台用户数据隔离规则。

### 2.3 后台通用列表查询

| 参数 | 说明 |
| --- | --- |
| `page_no` / `page_size` | 页码默认 1，每页默认 10、最大 100 |
| `order_by` | JSON 数组，如 `[{"id":"asc"}]`，默认按 ID 升序 |
| `created_time` / `updated_time` | 时间范围 `["start","end"]` |
| `created_id` / `updated_id` | 按后台创建人、更新人筛选 |

各资源的名称、状态、类型等筛选项以其查询模型为准。分页结果 `data` 包含 `page_no`、`page_size`、`total`、`has_next`、`items`；树形资源使用树结构，特殊分页以对应模块为准。

### 2.4 后台通用 CRUD

多数资源使用以下动作，路径需加模块前缀，例如 `/api/v1/system/user`。

| 方法 | 动作 | 说明 |
| --- | --- | --- |
| GET | `list` 或 `page` | 分页列表 |
| GET | `detail/{id}` | 单条详情 |
| POST | `create` | 新增，审计字段取当前后台管理员 |
| PUT | `update/{id}` | 修改单条 |
| DELETE | `delete` | 批量软删除，请求体为 ID 列表 |
| PATCH | `status/batch` | 批量启停，请求体含 `ids`、`status` |

资源是否支持树、启停或导出，以及特有动作，以各模块接口表为准。

### 2.5 前台用户响应与鉴权约定（待补充）

前台用户使用单独的一套响应和鉴权约定，与后台管理员身份及管理权限区分。此处仅确定需求方向，具体协议及实现留待前台用户模块开发时补充：

- **响应约定**：响应结构、业务错误码、分页及异常处理方式待定义。
- **鉴权约定**：注册与登录入口、令牌或会话机制、刷新与退出规则，以及与后台管理员身份的隔离方式待定义。
- **权限与数据归属**：个人资料与前台业务的访问边界待定义，不直接使用后台菜单、按钮权限或部门数据范围。

本节不代表上述独立机制已实现，也不预先指定前台接口路径、令牌字段或错误码。

---

# Part 2：后台业务模块需求

---

## 3. 认证模块

### 3.1 业务描述

提供后台管理员登录、会话管理、退出和忘记密码申请。支持账号密码，以及配置凭据后的 GitHub、Gitee、QQ、微信开放平台和小程序登录。

沿用第 2 节后台认证约定，账号使用 `sys_user`；前台用户独立认证待后续补充。

### 3.2 业务规则

- **账号校验**：账号须存在、未删除且启用，密码正确；超管同样需要认证。受保护请求持续校验令牌、会话和账号状态。
- **验证码与限流**：启用滑块验证码时，获取、完成和登录共用验证码状态；有效期及登录限流按配置执行。
- **登录成功**：更新最后登录时间，签发访问令牌和刷新令牌，建立 Redis 会话；业务访问按管理员权限控制。
- **刷新与退出**：刷新轮换令牌，失效刷新令牌重复使用时撤销会话；退出注销当前会话。
- **登录日志**：记录成功或失败结果、IP、地点、操作系统和浏览器；地点解析由 `ip_location_enable` 控制。
- **扩展渠道**：OAuth 与小程序登录需配置应用凭据；小程序支持 code、手机号登录及生成小程序码。
- **忘记密码**：按用户名登记申请，提示联系管理员重置，不直接改密；账号维护与重置规则见第 4 节。

### 3.3 数据模型

后台账号使用 `sys_user`，登录结果写入登录日志，不另建认证账号表。

Redis 的 `user_session` 以 `session_id` 关联后台账号 `user_id`，保存认证与权限上下文；JWT 的 `sub` 指向该会话。`access_token`、`refresh_token` 支持访问和续期，`captcha_codes` 保存验证码状态。

### 3.4 API 接口

以下为后台认证接口，统一添加 `/api/v1` 前缀。

| 方法 | 路径 | 需已登录 | 说明 |
| --- | --- | --- | --- |
| POST | `/system/auth/login` | 否 | 账号密码登录，返回双令牌、`token_type=Bearer`、`expires_in` |
| POST | `/system/auth/token/refresh` | 否 | 用刷新令牌轮换双令牌 |
| POST | `/system/auth/logout` | 是 | 注销当前会话 |
| GET / POST | `/system/auth/captcha/get`、`/system/auth/captcha/slider/complete` | 否 | 获取、完成滑块验证码 |
| GET | `/system/auth/oauth/{provider}/login` | 否 | 第三方授权，支持 github、gitee、qq、wechat |
| GET | `/system/auth/oauth/{provider}/callback` | 否 | 处理授权回调并登录 |
| POST | `/system/auth/wx-login` | 否 | 小程序 code 登录 |
| POST | `/system/auth/wx-phone-login` | 否 | 小程序手机号登录 |
| POST | `/system/auth/wx-qrcode/generate` | 是 | 生成小程序码 |
| POST | `/system/user/password/forget` | 否 | 忘记密码申请，不直接改密 |

---

## 4. RBAC 权限系统

管理后台管理员、角色和权限，控制可见菜单、页面操作及接口访问。管理员通过角色获得菜单和按钮上的 `permission`，多个启用角色的功能权限取并集；超管跳过权限检查。

角色同时配置 `data_scope`，配合第 5 节的部门组织确定数据范围；功能权限决定“能做什么”，数据范围决定“能访问哪些数据”。

### 4.1 用户

#### 业务描述

维护后台管理员账号，分配角色，关联组织管理中的部门和岗位，并提供个人资料、改密、导入导出。

#### 业务规则

- 用户名全局唯一。管理端创建：字母开头，2–32 位，仅字母、数字、下划线和 `._-`。注册接口最少 3 位，规则同上。
- 昵称必填。手机号 11 位且符合号段；邮箱填写时须为合法邮箱。性别：`0` 男，`1` 女，`2` 未知。
- 分配角色或岗位时，目标必须存在且启用。
- 当前用户可改自己的基本资料，并用旧密码修改新密码。管理员重置他人密码时，不能重置超级管理员。
- 不能删除超级管理员，也不能删除当前登录用户。删除前先解除角色、岗位关系，再软删除。
- 列表与导出走数据范围。导入按行返回失败原因，并提供模板下载。
- 编辑用户时，提交空角色列表会清空角色；不传该字段或传 `null` 则保持原角色。岗位同理。

#### 数据模型

**sys_user**：后台管理员账号。

| 关键字段 | 业务用途或关联 |
| --- | --- |
| `username` / `password` | 唯一登录账号与密码哈希 |
| `is_superuser` / `status` | 超管身份与账号启停，决定权限豁免及是否允许认证 |
| `dept_id` | 关联 `sys_dept.id`，用于部门数据范围 |
| `github_login` / `gitee_login` / `wx_login` / `qq_login` | 第三方认证身份绑定 |
| `last_login` | 登录成功时更新 |

`sys_user_roles(user_id, role_id)` 关联账号与角色；`sys_user_positions(user_id, position_id)` 关联账号与岗位，均为多对多关系。

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

**sys_role**：`code` 为唯一角色编码；`status` 控制授权是否生效；`data_scope` 决定本人、部门及子部门或全部数据范围。

**关联关系**：通过 `sys_user_roles(user_id, role_id)` 分配给账号，通过 `sys_role_menus(role_id, menu_id)` 关联权限节点。

`sys_role_depts(role_id, dept_id)` 为现有角色部门关联结构，保存授权时清空，不参与当前三档数据范围。

#### API 接口

前缀 `/system/role`。列表、详情、新增、修改、删除、批量启停使用通用 CRUD。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/system/role/options` | 可用角色下拉 |
| PUT | `/system/role/permission` | 替换菜单并保存数据范围。权限标识 `module_system:role:permission` |
| POST | `/system/role/export` | 导出角色 |

### 4.3 权限（菜单与按钮）

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

**sys_menu**：目录、菜单、按钮和外链的统一权限节点。

| 关键字段 | 业务用途或关联 |
| --- | --- |
| `parent_id` / `type` | 自关联菜单树与节点类型，决定父子层级及联动操作 |
| `permission` | 功能鉴权标识，通过 `sys_role_menus` 授权给角色 |
| `route_name` / `route_path` / `component_path` / `redirect` | 页面路由、组件和跳转配置 |
| `scope` / `status` | 可见端与节点启停，影响展示和授权 |
| `hidden` / `keep_alive` / `affix` | 菜单隐藏、页面缓存与固定标签 |
| `link` / `is_iframe` | 外链目标与打开方式 |

角色与节点通过 `sys_role_menus(role_id, menu_id)` 多对多关联。

#### API 接口

前缀 `/system/menu`。没有分页列表，用树代替。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/system/menu/tree` | 菜单树 |
| GET | `/system/menu/detail/{id}` | 详情 |
| POST / PUT / DELETE / PATCH | `create`、`update/{id}`、`delete`、`status/batch` | 通用维护。删除含后代；启停联动父子 |

---

## 5. 组织管理

管理部门和岗位，维护后台管理员的组织归属与职务。一个管理员最多属于一个部门，可关联多个岗位。

部门树为角色的数据范围提供组织依据，实际范围仍由角色 `data_scope` 决定；岗位仅作职务标记，不直接授予菜单权限或数据权限。

### 5.1 部门

#### 业务描述

部门以树形结构组织后台管理员。当角色 `data_scope = 2` 时，按管理员所属部门及子部门确定数据范围。

#### 业务规则

- 名称必填。编码全局唯一，规则同角色编码。
- 存在子部门时不能删除父部门。
- 批量启用时联动上级，批量停用时联动下级。
- `parent_id` 为空表示顶级。

#### 数据模型

**sys_dept**：`code` 唯一标识部门，`parent_id` 自关联形成部门树，`status` 控制启停与父子联动。

账号通过 `sys_user.dept_id` 归属部门；角色 `data_scope = 2` 时沿部门树计算可访问范围。

#### API 接口

前缀 `/system/dept`。用 `tree` 代替分页列表，其余为详情、新增、修改、删除、批量启停。

### 5.2 岗位

#### 业务描述

岗位是独立于部门树的职务目录，只用于给用户打标，不参与数据范围。

#### 业务规则

- 名称必填。编码全局唯一，规则同角色编码。
- 可按状态取下拉选项，并导出 Excel。

#### 数据模型

**sys_position**：`code` 为唯一岗位编码，`status` 决定是否可选。

通过 `sys_user_positions(user_id, position_id)` 与后台账号多对多关联，不参与功能授权或数据范围。

#### API 接口

前缀 `/system/position`。列表、详情、新增、修改、删除、批量启停使用通用 CRUD。另有 `GET options` 与 `POST export`。

---

## 6. 配置与字典

### 6.1 字典管理

#### 业务描述

字典为页面上的下拉、标签和状态色提供选项。类型和条目分开维护，启动时写入 Redis，按类型编码读取。

#### 业务规则

- 类型编码 `dict_type` 全局唯一。
- 条目通过 `dict_type_id` 归属类型，同时冗余 `dict_type` 编码供查询。
- 条目可标记默认项，并用 `list_class`、`css_class` 控制表格展示。
- 类型与条目都可批量启停。

#### 数据模型

| 模型 | 关键字段与业务关联 |
| --- | --- |
| `sys_dict_type` | `dict_type` 为唯一类型编码和读取键；`status` 控制启停 |
| `sys_dict_data` | `dict_type_id` 关联类型，`dict_type` 冗余其编码；`dict_label` / `dict_value` 定义显示与存储映射，`is_default` 标记默认项，`status` 控制启停 |

字典类型与条目为一对多关系；删除类型时级联删除条目。

#### API 接口

类型前缀 `/system/dict/type`，条目前缀 `/system/dict/data`。两边都使用通用 CRUD（含批量启停）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/system/dict/type/optionselect` | 类型下拉 |
| GET | `/system/dict/data/info/{dict_type}` | 按类型编码读取条目 |

### 6.2 参数管理

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

**sys_param**：`config_key` 为不可修改的读取键，`config_value` 保存配置值，`config_type` 标识内置项，`status` 控制启停。

参数修改同步 Redis，供页面及请求中间件读取。本模块不提供通用新增和删除接口。

#### API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/system/param/info` | 从缓存读取参数 |
| PUT | `/system/param/update/{id}` | 修改参数值并刷新缓存 |

---

## 7. 内容与其他

本节简述通用内容与辅助管理能力，响应、鉴权及常规维护遵循第 2 节。

### 7.1 日志管理

记录后台登录结果和操作请求，支持查询、删除及操作日志导出。

- **规则**：登录状态 `1` 成功、`2` 失败；操作状态 `0` 成功、`1` 失败。操作日志保留请求、响应、耗时和来源 IP。
- **关键模型**：`sys_login_log`、`sys_operation_log` 以 `username` 保存操作人快照，不通过用户审计外键关联账号；`status` 记录结果。
- **接口入口**：`/system/log/login`、`/system/log/operation`，提供列表、详情、删除；操作日志另有 `export`。

### 7.2 公告管理

维护通知与公告，并通过 SSE 通知在线客户端刷新。

- **规则**：标题必填且不能重复，正文做 HTML 清理；`notice_type` 区分通知和公告，`status` 为 `0` 草稿、`1` 已发布、`2` 已归档。
- **关键模型**：`sys_notice`，保留 `notice_title`、`notice_content`、`notice_type`、`status` 等业务字段。
- **接口入口**：`/system/notice`，提供通用维护、`available` 和 `stream`。当前 `available` 按 `status = 0` 返回最多 10 条；变更广播 `notice_update`。

### 7.3 工单管理

接收建议、缺陷、优化等反馈，支持指派、回复、评论和状态处理。

- **规则**：状态为 `0` 待处理、`1` 处理中、`2` 已完成、`3` 已关闭；流转按创建人、处理人和超管身份校验，已关闭工单仅超管可重新打开。处理人须在当前操作者可查询范围内，批量流转逐条校验。
- **关键模型**：`sys_ticket.created_id`、`assigned_id` 关联提交人与处理人；`status` 控制流转。`sys_ticket_comment.ticket_id` 关联工单，删除工单时级联删除评论。
- **接口入口**：`/system/ticket`，提供列表、详情、维护、统计、批量流转、导出及评论。

### 7.4 版本管理

维护版本说明、发布状态，以及是否要求客户端重新登录。

- **规则**：版本号唯一；`status` 为 `0` 草稿、`1` 已发布、`2` 已回滚；公开版本查询只返回已发布项，`require_re_login` 标记是否要求结束客户端会话。
- **关键模型**：`sys_version`，关键字段为 `version`、`status`、`require_re_login`。
- **接口入口**：`/system/versions`，提供通用维护、`published` 查询和 `/{id}/status` 状态更新。

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

| 模型 | 关键字段与执行流程 |
| --- | --- |
| `task_cornjob_node` | `code` 为唯一节点编码；`func`、`args` / `kwargs` 定义执行内容；`trigger` / `trigger_args` 与 `start_date` / `end_date` 定义计划，`status` 控制启停，`coalesce` / `max_instances` 控制合并与并发 |
| `task_corn_job` | `job_id` 关联调度任务标识，节点执行记录归一到所属节点 ID；`trigger_type` 区分计划或手动执行，`status` 记录执行阶段，`result` / `error` 保存结果与失败原因 |

节点定义可重复执行的计划，执行日志记录每次结果；`job_id` 是调度标识，不是数据库外键。

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

**task_storage_node**：供浏览、传输和流程节点复用的连接配置。

| 关键字段 | 业务用途或关联 |
| --- | --- |
| `name` / `protocol` | 名称唯一；协议决定连接校验和存储适配器 |
| `host` / `port`、`username` / `password` | 主机连接与认证，密码或密钥加密保存 |
| `bucket` / `endpoint` / `region` / `path_prefix` | 对象存储定位与起始路径，按协议使用 |
| `is_default` / `status` | 默认源选择与可用性 |
| `multipart_part_size` / `multipart_concurrency` | 分片默认参数，可被传输步骤或流程连线覆盖 |

传输任务、步骤和流程节点通过存储源 ID 引用本模型，由业务层校验可用性。

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

不单独建表。通过 `source_id` 选择 `task_storage_node`，结合桶和路径读写目标文件或目录。

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

| 模型 | 关键字段与业务关联 |
| --- | --- |
| `task_storage_transfer` | `task_type` 决定并行或链式，`source_type` 区分本地或远端；`source_id` / `source_path` 定位源，`status` 驱动执行与取消，`progress`、`total_size` / `transferred_size` 记录进度，`error_msg` 保存失败原因 |
| `task_storage_transfer_step` | `task_id` 关联任务，`step_order` 定义步骤顺序；`source_id` / `source_path` 与 `target_id` / `target_path` 定位两端，`transfer_mode`、`multipart_part_size` / `multipart_concurrency` 控制传输方式；`status`、`progress`、`error_msg` 记录步骤结果 |

一个任务包含多个步骤；删除任务时级联删除步骤。存储源 ID 为业务引用；本地源的 `source_id` 可空，`source_path` 指向服务端临时文件。

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

| 模型 | 关键字段与业务关联 |
| --- | --- |
| `task_storage_workflow` | `task_type` 决定并行或链式，`status` 控制启停；`graph` 只存布局，业务配置以节点和连线为准 |
| `task_storage_workflow_node` | `flow_id` 归属流程，`node_key` 标识节点；`source_id` 引用存储源，`source_path` 定义默认路径 |
| `task_storage_workflow_edge` | `flow_id` 归属流程，`edge_key` 标识连线；`source_node_key` / `target_node_key` 连接同一流程内的节点，`enabled` 决定是否执行，`transfer_mode`、`multipart_part_size` / `multipart_concurrency` 定义传输配置 |

流程、节点、连线及存储源之间的引用由业务层维护。连线目标路径取目标节点的 `source_path`，执行时按启用连线创建传输任务。

#### API 接口

前缀 `/task/storage/workflow`。分页、简表、详情、新增、修改、删除使用通用 CRUD。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/task/storage/workflow/execute/{id}` | 按启用连线创建传输任务 |

---

## 10. 代码生成

### 10.1 业务描述

从当前数据库导入表，或提交建表 SQL，编辑字段在列表、表单、查询中的表现，然后预览并输出管理端代码。

### 10.2 业务规则

- 表名、实体类名、列名、列类型不能为空。
- 字段可标记主键、自增、可空、唯一，以及是否出现在新增、编辑、列表、查询中。
- `query_type` 决定查询方式，`html_type` 决定表单组件，`dict_type` 绑定字典。
- 支持主表关联子表（`sub_table_name`、`sub_table_fk_name`）和挂到指定父菜单（`parent_menu_id`）。
- 预览不写文件。单表输出写到生成路径；批量输出打包下载。
- 同步数据库前可以先看差异。创建表接口接收 SQL，由生成服务校验后落库。

### 10.3 数据模型

| 模型 | 关键字段与生成流程 |
| --- | --- |
| `gen_table` | `table_name` / `class_name` 标识目标表与实体；`sub_table_name` / `sub_table_fk_name` 定义主子表关系，`parent_menu_id` 指定生成菜单的父节点 |
| `gen_table_column` | `table_id` 关联表配置；`column_name` / `column_type` 与 `python_field` / `python_type` 定义数据库和代码映射；`is_pk` / `is_increment` / `is_nullable` / `is_unique` 定义约束；`is_insert` / `is_edit` / `is_list` / `is_query` 控制页面行为，`query_type` / `html_type` / `dict_type` 决定查询、控件和字典绑定 |

表配置与字段配置为一对多关系，删除表配置时级联删除字段；子表名、父菜单 ID 和字典编码用于生成关联配置。

### 10.4 API 接口

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

## 11. 监控与公共文件

### 11.1 业务描述

提供健康检查、本机资源、在线会话、Redis 缓存和基础统计，以及受权限控制的公共上传下载。

### 11.2 业务规则

- 健康检查执行数据库 `SELECT 1` 和 Redis `PING`，返回服务名、版本、环境和连接结果。
- 服务器信息包含 CPU、内存、磁盘、操作系统和 Python 运行信息。
- 在线会话来自 Redis。可按名称、IP、登录地点过滤，可查看本人会话、强制下线指定会话或清空在线会话。
- 缓存监控可查看 Redis 信息、缓存名、键和值，并清理指定缓存名、指定键或全部缓存。清理全部缓存需要独立权限。
- 基础统计包含在线人数、用户数和近期登录等指标。
- 公共上传返回文件名、映射路径和访问地址。下载按映射路径读取受控文件。上传、下载各自有权限标识。

### 11.3 数据模型

无独立业务表。在线管理读取 Redis `user_session`：`session_id` 选择会话，`user_id` 关联后台账号；`is_superuser` / `user_status`、`permissions` / `menu_ids`、`dept_id` 支持身份、授权和数据范围上下文。强制下线按会话撤销。

### 11.4 API 接口

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

## 12. 示例插件

### 12.1 业务描述

仓库内的示例插件用来验证插件约定：启动时发现 `app/plugin/module_*/**/controller.py` 并注册路由。它不是独立业务。

### 12.2 业务规则

- 示例记录支持详情、分页、增删改、启停，以及 Excel 导入、导出和模板下载。
- 字段覆盖常用类型，便于对照代码生成和表单组件，不承载产品数据。

### 12.3 数据模型

**example_demo**：`status` 支持启停；其余为基础类型演示字段，不涉及业务关联，不在 PRD 中逐项列出。

### 12.4 API 接口

前缀 `/example/demo`。列表、详情、新增、修改、删除、批量启停使用通用 CRUD。另有 `POST export`、`import`、`download/template`。

---

## 13. 模块关系

```text
用户 ──多对多── 角色 ──多对多── 菜单（permission = 鉴权键）
  │              │
  │              └── data_scope：1 本人 / 2 本部门及以下 / 3 全部
  ├── 属于一个部门（部门树决定范围 2）
  ├── 多对多岗位（不参与数据范围）
  ├── 产生登录日志、操作日志
  └── 提交工单，并可被指派为处理人

字典类型 ──一对多── 字典条目
系统参数 ──写入 Redis── 站点文案、演示模式、IP 黑白名单

任务节点 ──调度── 执行日志
存储源 ──被使用于── 文件浏览、传输步骤、流程节点
传输流程 ──执行时创建── 传输任务 ──展开为── 传输步骤

代码生成配置 ──一对多── 字段配置 ──输出── 管理端代码
示例插件 ──独立于── 上述业务，只验证插件加载
```

RBAC 功能权限来自菜单和按钮节点的 `permission`；数据范围由角色 `data_scope` 与部门组织共同确定，岗位不参与授权。超管跳过两种检查。文件传输的进度以任务和步骤表为准，SSE 只做推送。
