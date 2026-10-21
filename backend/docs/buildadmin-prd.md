# BuildAdmin 产品需求文档

| 项 | 说明 |
| --- | --- |
| 产品 | BuildAdmin 后台管理系统（含会员中心） |
| 版本 | v2.3.9 |
| 技术栈 | 后端 PHP 8 + ThinkPHP 8 + MySQL；前端 Vue 3 + Element Plus + TypeScript + Vite + Pinia |
| 应用划分 | `admin` 后台管理、`api` 会员端与公共接口、`common` 共享基类（不可通过 Web 访问） |
| 文档范围 | 本仓库已实现的内置模块。模块市场安装的第三方模块不在本文范围 |

## 1. 产品概述

BuildAdmin 是一套前后端分离的商业级后台管理系统。它提供管理员与会员两套账号体系、无限层级的菜单与按钮权限、系统配置、附件、数据回收与字段级修改保护、可视化 CRUD 代码生成、模块安装，以及会员中心的资料、余额和积分能力。

产品同时服务两类用户：

- **后台管理员**：登录后台，按角色组权限管理菜单、人员、会员、配置、安全和开发工具。
- **前台会员**：在会员中心注册、登录、维护资料、查看余额与积分流水。会员中心可由配置关闭。

后台菜单、页面和按钮由权限节点动态注册。会员中心的路由、顶栏和按钮由会员权限规则动态注册。

## 2. 全局约定

### 2.1 业务描述

所有接口共用同一套响应、鉴权和列表查询约定。后台接口默认要求管理员登录并校验权限节点；会员接口默认要求会员登录并校验会员权限节点。

### 2.2 业务规则

- 统一响应：`{ code, msg, time, data }`。`code == 1` 表示成功。
- 未登录返回 `code = 303`，`data.type` 标识需要登录。
- Token 过期返回 `code = 409`，前端用刷新 Token 换取新的访问 Token 后重放请求。
- 已登录但无权限节点返回 `code = 401`。
- 后台访问 Token 放在请求头 `batoken`，类型为 `admin`。勾选「保持登录」时同时签发 `admin-refresh`。
- 会员访问 Token 放在请求头 `ba-user-token`，类型为 `user`。保持登录时同时签发 `user-refresh`。
- 访问 Token 默认有效 3 天（`admin_token_keep_time` / `user_token_keep_time`）。刷新 Token 的有效期由保持登录时长决定。
- 开启单点登录（`admin_sso` / `user_sso`，默认关闭）后，新登录会清掉该账号同类型的旧 Token。
- 登录失败次数达到 `admin_login_retry` / `user_login_retry`（默认 10）后，需等待 24 小时才可再次尝试。距上次登录已满 24 小时会清零失败次数。配置为 `false` 时不限制。
- 密码使用 `hash_password` 存储，长度 6–32，且不能包含 `& < > " ' ` 及换行。`salt` 字段已废弃，重置密码时写空字符串。
- 管理员登录点选验证码由 `admin_login_captcha` 控制，会员登录点选验证码由 `user_login_captcha` 控制，默认均开启。
- 超级管理员的判定是：其所在角色组的权限规则为 `*`。
- 后台 POST / DELETE 在 `auto_write_admin_log` 开启时自动写入管理员日志。
- 时间字段为 Unix 秒级时间戳（`biginteger`），由模型自动写入 `create_time` / `update_time`。
- 金额在库内以「分」的整数保存，读写时按 100 换算为两位小数的元。

数据权限（后台控制器 `$dataLimit`）：

| 取值 | 含义 |
| --- | --- |
| `false` | 不限制 |
| `personal` | 仅本人数据 |
| `allAuth` | 拥有某管理员全部权限时可看该管理员的数据 |
| `allAuthAndOthers` | 拥有某管理员全部权限且自己还有额外权限时可看 |
| `parent` | 上级分组中的管理员可看 |
| 分组 ID | 指定分组内的管理员可看 |

启用数据权限时，数据表需有对应字段（默认 `admin_id`）。管理员模块把限制字段设为 `id`。

### 2.3 通用列表查询

后台继承 `Backend` trait 的列表接口接受以下参数：

| 参数 | 说明 |
| --- | --- |
| `quickSearch` | 按控制器配置的字段做模糊搜索 |
| `search` | 组合条件数组，每项含 `field`、`operator`、`val`，可选 `render` |
| `order` | 排序 |
| `limit` | 每页条数，默认 10 |
| `page` | 页码 |
| `initKey` / `initValue` / `initOperator` | 远程下拉回显，默认按主键 `IN` |
| `select` | 为真时走远程下拉 `select`，返回 `options` |

`search.operator` 支持：`=`、`<>`、`LIKE`、`NOT LIKE`、`>`、`>=`、`<`、`<=`、`RANGE`、`NOT RANGE`、`IN`、`NOT IN`、`FIND_IN_SET`、`NULL`、`NOT NULL`。`render=datetime` 时按时间戳比较。

列表成功响应：`data.list`、`data.total`，多数接口附带 `data.remark`（路由备注）。

### 2.4 通用 CRUD 接口

路径形如 `/admin/{控制器}/{动作}`。多级控制器使用点号，例如 `/admin/auth.Admin/index`。未单独重写的动作使用下表语义。

| 方法 | 动作 | 说明 |
| --- | --- | --- |
| GET | `index` | 分页列表；带 `select` 时返回下拉选项 |
| POST | `add` | 新增。受模型场景验证约束，排除时间戳等字段 |
| GET | `edit` | 读取单条，参数为主键 |
| POST | `edit` | 保存单条 |
| DELETE / POST | `del` | 批量删除，参数 `ids` 为数组 |
| POST | `sortable` | 拖拽排序，依赖 `weigh` 字段 |

下文各模块只列出相对通用 CRUD 的差异和该模块特有接口。

### 2.5 鉴权头与入口

| 端 | 前缀 | 身份头 |
| --- | --- | --- |
| 后台 | `/admin/` | `batoken` |
| 会员与公共 | `/api/` | `ba-user-token`（需要登录的接口） |

后台入口路径默认 `/admin`，可在系统配置中改为 `/` 加字母数字（`backend_entrance`）。非默认入口时，前端把 `/admin/...` 重写到 `{入口}.php/...`。

---

## 3. 后台登录与控制台

### 3.1 业务描述

管理员通过用户名和密码进入后台。登录成功后，初始化接口返回当前管理员、其可见菜单和站点配置，前端据此注册路由。控制台是登录后的首页，展示欢迎语和本地记录的当日工作时长。

### 3.2 业务规则

- 用户名长度 3–30。密码规则见全局约定。
- 已登录再次访问登录接口时，返回已登录状态，`code = 303`。
- 账号 `status = disable` 不可登录。
- 用户名不存在、密码错误分别返回对应错误；密码错误累加 `login_failure`。
- 开启点选验证码时，必须提交 `captchaId`、`captchaInfo` 并通过校验。
- 退出时删除本次刷新 Token（仅当它属于当前管理员且类型为 `admin-refresh`），并作废当前访问 Token。
- 初始化时若没有任何可见菜单，拒绝进入后台。
- 控制台统计卡片（会员注册、附件数、会员总数、插件数）是前端示例数字，不读取业务库。工作时长保存在浏览器本地，可暂停与继续，跨天重置。

### 3.3 数据模型

登录与菜单数据见「权限管理」「系统配置」。本模块不单独建表。Token 见「公共能力」。

### 3.4 API 接口

| 方法 | 路径 | 登录 | 说明 |
| --- | --- | --- | --- |
| GET | `/admin/Index/login` | 否 | 返回是否开启登录验证码 |
| POST | `/admin/Index/login` | 否 | 登录。参数：`username`、`password`、`keep`，以及可选验证码字段。成功返回 `userInfo`（含 token） |
| POST | `/admin/Index/logout` | 否（有 Token 时注销） | 参数：`refreshToken` |
| GET | `/admin/Index/index` | 是，不校验节点 | 返回 `adminInfo`、`menus`、`siteConfig`、`terminal` |
| GET | `/admin/Dashboard/index` | 是 | 返回当前路由备注 `remark` |

`siteConfig` 含站点名、版本号、模块中心地址、上传限制、CDN 地址。`terminal` 含是否为 PHP 内置服务器、npm 包管理器名称。

---

## 4. 权限管理

权限管理包含管理员、角色组、菜单规则和管理员日志。角色组是树形结构，菜单规则也是树形结构。管理员通过 `admin_group_access` 加入一个或多个角色组，权限取各组规则的并集。

### 4.1 管理员

#### 业务描述

维护可登录后台的账号，并指定其所属角色组。

#### 业务规则

- 用户名：以字母开头，3–16 位，仅字母、数字、下划线，全局唯一。
- 昵称必填。邮箱、手机号可空，填写时格式合法且唯一。
- 新增必须选择至少一个角色组，并设置密码。
- 列表与改删受数据权限 `allAuthAndOthers` 约束，限制字段为管理员 `id`。非超管只能把管理员加入自己有权管理的角色组。
- 不能禁用当前登录账号，需使用其他管理员操作。
- 不能删除当前登录账号。删除管理员时同步删除其角色组关联。
- 列表不返回密码、盐和登录失败次数。编辑回显时密码为空。
- 修改密码走 `resetPassword`，不把明文密码写入普通字段。
- 快速搜索：用户名、昵称。

#### 数据模型

**admin 管理员表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 管理员 ID |
| username | varchar(20) unique | 用户名 |
| nickname | varchar(50) | 昵称 |
| avatar | varchar(255) | 头像路径，空则使用默认头像 |
| email | varchar(50) | 邮箱 |
| mobile | varchar(11) | 手机 |
| login_failure | tinyint unsigned | 登录失败次数 |
| last_login_time | bigint unsigned | 上次登录时间 |
| last_login_ip | varchar(50) | 上次登录 IP |
| password | varchar(255) | 密码密文 |
| salt | varchar(30) | 密码盐，已废弃 |
| motto | varchar(255) | 签名 |
| status | varchar(30) | `enable` 启用，`disable` 禁用，可扩展其他状态 |
| update_time / create_time | bigint unsigned | 更新 / 创建时间 |

**admin_group_access 管理员与角色组关联**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| uid | int unsigned | 管理员 ID，索引 |
| group_id | int unsigned | 角色组 ID，索引 |

接口附加只读属性：`group_arr`（角色组 ID 列表）、`group_name_arr`（角色组名称列表）。

#### API 接口

控制器：`/admin/auth.Admin/`。使用通用 CRUD。

| 差异 | 说明 |
| --- | --- |
| GET `index` | 去掉密码、盐、失败次数字段 |
| POST `add` | 额外写入角色组关联，再重置密码 |
| GET/POST `edit` | 校验数据权限；保存时重建角色组关联 |
| `del` | 跳过当前账号，并清理关联 |

### 4.2 角色组

#### 业务描述

角色组决定管理员能看到的菜单和能调用的按钮。组与组之间是无限级父子关系。

#### 业务规则

- 组名必填。`status`：`1` 启用，`0` 禁用。
- `rules` 保存菜单规则 ID，逗号分隔。勾选全部规则时存 `*`，表示超级管理员组。
- 只有超级管理员可以创建 `*` 组。
- 不能创建「拥有自己全部权限」的组，也不能写入超出自己权限的规则 ID。不存在的规则 ID 会被丢弃。
- 不能修改、删除自己所在的角色组。
- 删除前必须先删除或一并提交子组，否则拒绝。
- 修改、删除时按 `allAuthAndOthers` 校验操作者对该组是否有管理权。
- 列表默认组装为树。远程下拉只返回启用组；带初始化值时不组装树。
- 快速搜索：组名。

#### 数据模型

**admin_group 管理分组表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 分组 ID |
| pid | int unsigned | 上级分组，0 为顶级 |
| name | varchar(100) | 组名 |
| rules | text | 权限规则 ID，或 `*` |
| status | tinyint / boolean | `0` 禁用，`1` 启用 |
| update_time / create_time | bigint unsigned | 更新 / 创建时间 |

#### API 接口

控制器：`/admin/auth.Group/`。

| 方法 | 动作 | 说明 |
| --- | --- | --- |
| GET | `index` | 返回树形 `list`、当前管理员的 `group` ID 列表 |
| POST | `add` | 新增。`rules` 为 ID 数组 |
| GET/POST | `edit` | 读取时去掉父节点 ID，便于树勾选；保存时重算 `rules` |
| `del` | `del` | 批量删除，含子组校验 |
| GET | `select` | 启用分组的远程下拉 |

### 4.3 菜单与权限规则

#### 业务描述

后台的目录、菜单项和按钮都是权限节点。前端用菜单节点注册路由，用按钮节点控制页面内操作。节点名称即鉴权键，形如 `auth/admin/index`。

#### 业务规则

- 类型 `type`：`menu_dir` 菜单目录、`menu` 菜单项、`button` 页面按钮。
- 菜单打开方式 `menu_type`：`tab` 选项卡、`link` 外链、`iframe` 内嵌页。
- 扩展 `extend`：`none` 正常；`add_rules_only` 只注册路由不显示菜单；`add_menu_only` 只显示菜单不注册权限。
- `name` 为规则名称，同时作为权限校验键。`path` 为前端路由路径，`component` 为 Vue 组件路径。
- `keepalive = 1` 时标签页缓存该页面。
- `weigh` 越大越靠前。`status = 0` 的节点不参与菜单与鉴权。
- 删除前需先删除子节点，或使用包含子节点的批量删除。
- 快速搜索按规则名称等常规字段。树形展示。

#### 数据模型

**admin_rule 菜单和权限规则表**（历史表名 `menu_rule`）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 规则 ID |
| pid | int unsigned | 上级菜单，索引 |
| type | enum | `menu_dir` / `menu` / `button` |
| title | varchar(50) | 标题 |
| name | varchar(50) | 规则名称（鉴权键） |
| path | varchar(100) | 路由路径 |
| icon | varchar(50) | 图标 |
| menu_type | enum | `tab` / `link` / `iframe` |
| url | varchar(255) | 外链或 iframe 地址 |
| component | varchar(100) | 组件路径 |
| keepalive | tinyint unsigned | 是否缓存 |
| extend | enum | `none` / `add_rules_only` / `add_menu_only` |
| remark | varchar(255) | 备注，列表接口可作为页面说明返回 |
| weigh | int | 权重 |
| status | tinyint | `0` 禁用，`1` 启用 |
| update_time / create_time | bigint unsigned | 更新 / 创建时间 |

#### API 接口

控制器：`/admin/auth.Rule/`。提供树形 `index`、`add`、`edit`、`del`、`select`，语义同通用 CRUD，删除含子节点校验。

### 4.4 管理员日志

#### 业务描述

记录管理员在后台的写操作，用于审计。日志由中间件在 POST / DELETE 请求结束后自动写入。

#### 业务规则

- `auto_write_admin_log = false` 时不记录。
- 记录操作者 ID、用户名、URL、标题、请求数据、IP、User-Agent。
- 非超级管理员只能查看自己的日志。
- 快速搜索：日志标题。
- 登录动作会把标题设为「登录」。

#### 数据模型

**admin_log 管理员日志表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 日志 ID |
| admin_id | int unsigned | 管理员 ID |
| username | varchar(20) | 管理员用户名 |
| url | varchar(1500) | 操作 URL |
| title | varchar(100) | 日志标题 |
| data | longtext | 请求数据 |
| ip | varchar(50) | IP |
| useragent | varchar(255) | User-Agent |
| create_time | bigint unsigned | 创建时间 |

#### API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/auth.AdminLog/index` | 分页列表。超管看全部，其他人只看自己 |

个人资料页另有当前管理员自己的日志查询，见「个人资料」。

---

## 5. 会员

会员模块包含后台的会员、会员组、会员菜单规则、余额流水、积分流水，以及前台会员中心。会员权限与后台权限相互独立。

### 5.1 会员资料（后台）

#### 业务描述

后台管理员维护站点会员账号，指定会员组，并可重置密码。余额和积分不在会员表单里直接改，必须通过流水入账。

#### 业务规则

- 用户名规则与管理员相同，且在 `user` 表唯一。邮箱、手机号各自唯一（空字符串在唯一索引下需按安装数据约定处理）。
- 性别：`0` 未知，`1` 男，`2` 女。
- 状态：`enable` 启用，`disable` 禁用。禁用账号不能登录。注册默认 `enable`，默认会员组 ID 为 1。
- 昵称：若用户名中含手机号，注册时自动脱敏为 `前三****后四`。
- 列表不返回密码和盐。新增、编辑时密码单独重置。
- 快速搜索：用户名、昵称、ID。列表关联会员组。
- 注册时写入加入 IP、加入时间，并直接签发登录 Token。

#### 数据模型

**user 会员表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 会员 ID |
| group_id | int unsigned | 会员组 ID |
| username | varchar(32) unique | 用户名 |
| nickname | varchar(50) | 昵称 |
| email | varchar(50) unique | 邮箱 |
| mobile | varchar(11) unique | 手机 |
| avatar | varchar(255) | 头像 |
| gender | tinyint unsigned | `0` 未知，`1` 男，`2` 女 |
| birthday | date | 生日，可空 |
| money | int unsigned | 余额，单位分 |
| score | int unsigned | 积分 |
| last_login_time | bigint unsigned | 上次登录时间 |
| last_login_ip | varchar(50) | 上次登录 IP |
| login_failure | tinyint unsigned | 登录失败次数 |
| join_ip | varchar(50) | 注册 IP |
| join_time | bigint unsigned | 注册时间 |
| motto | varchar(255) | 签名 |
| password | varchar(255) | 密码密文 |
| salt | varchar(30) | 已废弃 |
| status | varchar(30) | `enable` / `disable`，可扩展 |
| update_time / create_time | bigint unsigned | 更新 / 创建时间 |

#### API 接口

控制器：`/admin/user.User/`。通用 CRUD。`index` 隐藏密码和盐；`add` / `edit` 对密码调用重置。

### 5.2 会员组

#### 业务描述

会员组把一组前台权限规则赋给会员。一个会员只属于一个组。

#### 业务规则

- 组名必填。`status`：`1` 启用，`0` 禁用。
- `rules` 为会员规则 ID，逗号分隔。勾选全部规则时存 `*`。
- 编辑回显时去掉父节点 ID，由子节点决定父级勾选。
- 快速搜索：组名。

#### 数据模型

**user_group 会员组表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 组 ID |
| name | varchar(50) | 组名 |
| rules | text | 权限节点 ID，或 `*` |
| status | tinyint | `0` 禁用，`1` 启用 |
| update_time / create_time | bigint unsigned | 更新 / 创建时间 |

#### API 接口

控制器：`/admin/user.Group/`。通用 CRUD，`add` / `edit` 会把全选规则写成 `*`。

### 5.3 会员菜单规则

#### 业务描述

定义会员中心的路由、菜单、顶栏和按钮。未登录用户仍可使用标记为「未登录有效」的路由、顶栏和按钮。

#### 业务规则

- 类型 `type`：`route` 路由、`menu_dir` 菜单目录、`menu` 菜单项、`nav_user_menu` 顶栏会员菜单下拉项、`nav` 顶栏菜单项、`button` 页面按钮。
- `menu_type`、`extend`、`weigh`、`status` 语义与后台菜单规则相同。
- `no_login_valid = 1` 时，未登录初始化只下发 `route`、`nav`、`button` 三类且状态启用的节点。
- 已登录时，菜单目录进入 `menus`，其余类型进入 `rules`，会员中心菜单项不放进首页规则列表。
- 删除含子节点校验。

#### 数据模型

**user_rule 会员菜单权限规则表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 规则 ID |
| pid | int unsigned | 上级，索引 |
| type | enum | `route` / `menu_dir` / `menu` / `nav_user_menu` / `nav` / `button` |
| title | varchar(50) | 标题 |
| name | varchar(50) | 规则名称 |
| path | varchar(100) | 路由路径 |
| icon | varchar(50) | 图标 |
| menu_type | enum | `tab` / `link` / `iframe` |
| url | varchar(255) | URL |
| component | varchar(100) | 组件路径 |
| no_login_valid | tinyint unsigned | `0` 否，`1` 未登录仍有效 |
| extend | enum | `none` / `add_rules_only` / `add_menu_only` |
| remark | varchar(255) | 备注 |
| weigh | int | 权重 |
| status | tinyint | `0` 禁用，`1` 启用 |
| update_time / create_time | bigint unsigned | 更新 / 创建时间 |

#### API 接口

控制器：`/admin/user.Rule/`。树形通用 CRUD：`index`、`add`、`edit`、`del`、`select`。

### 5.4 余额

#### 业务描述

管理员通过新增一条余额变动记录来增减会员余额。会员在会员中心查看自己的余额流水和近 7 日汇总。

#### 业务规则

- 余额不能在会员资料里直接修改。插入 `user_money_log` 时锁定会员行，写入变更前余额，把变动额加到会员余额，再写入变更后余额。
- 变动额可为正（增加）或负（扣减）。备注 `memo` 必填。
- 流水禁止删除（模型 `onBeforeDelete` 返回 false）。
- 库内为分，接口展示为元，保留两位小数。
- 后台快速搜索：会员用户名、昵称。新增页需先按 `userId` 找到会员。

#### 数据模型

**user_money_log 会员余额变动表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 记录 ID |
| user_id | int unsigned | 会员 ID |
| money | int | 变更金额，单位分，可为负 |
| before | int | 变更前余额，单位分 |
| after | int | 变更后余额，单位分 |
| memo | varchar(255) | 备注，必填 |
| create_time | bigint unsigned | 创建时间 |

#### API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/user.MoneyLog/index` | 后台分页，关联会员 |
| GET | `/admin/user.MoneyLog/add?userId=` | 返回目标会员信息 |
| POST | `/admin/user.MoneyLog/add` | 新增流水并改余额。参数：`user_id`、`money`、`memo` |
| GET | `/api/account/balance` | 会员查看自己的流水。参数：`page`、`limit` |
| GET | `/api/account/overview` | 近 7 日每日积分合计与余额合计（元） |

### 5.5 积分

#### 业务描述

积分的增减方式与余额相同：只通过流水入账，流水不可删。

#### 业务规则

- 插入前锁定会员，记录变更前积分，累加 `score`，再记录变更后积分。
- `memo` 必填。`score` 可为负。
- 积分按整数计，不做金额换算。

#### 数据模型

**user_score_log 会员积分变动表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 记录 ID |
| user_id | int unsigned | 会员 ID |
| score | int | 变更积分，可为负 |
| before | int | 变更前积分 |
| after | int | 变更后积分 |
| memo | varchar(255) | 备注，必填 |
| create_time | bigint unsigned | 创建时间 |

#### API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/user.ScoreLog/index` | 后台分页，关联会员 |
| GET | `/admin/user.ScoreLog/add?userId=` | 返回目标会员 |
| POST | `/admin/user.ScoreLog/add` | 新增流水并改积分 |
| GET | `/api/account/integral` | 会员查看自己的积分流水 |

### 5.6 前台会员中心

#### 业务描述

会员在前台完成注册、登录、资料维护、绑定邮箱或手机、修改密码、找回密码，并查看余额与积分。`open_member_center = false` 时会员中心关闭。

#### 业务规则

- 登录账号可以是用户名、邮箱或手机号，系统按格式自动判断字段。
- 注册方式 `registerType` 为 `email` 或 `mobile`，必须校验对应验证码（事件 `user_register`）。
- 注册用户名、密码规则见全局约定。邮箱或手机按注册方式必填且唯一。
- 已登录用户再次签入返回已登录，`code = 303`。
- 修改资料可改头像、用户名、昵称、性别、生日、签名。
- 已绑定邮箱或手机时，改绑前必须先完成账户验证，拿到 10 分钟有效的 `email-pass` 或 `mobile-pass` Token。未绑定时改为校验当前密码。
- 新邮箱、新手机号必须唯一，并校验事件 `user_change_email` / `user_change_mobile` 的验证码。
- 修改密码需验证旧密码。成功后注销当前登录，要求重新登录。
- 找回密码无需登录。按邮箱或手机找到账号后，校验 `user_retrieve_pwd` 验证码，再重置密码。
- 账户概览按自然日汇总最近 7 天（含当天）的积分变动合计和余额变动合计。

#### 数据模型

使用 `user`、`user_money_log`、`user_score_log`、`token`、`captcha`。

#### API 接口

| 方法 | 路径 | 登录 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/index/index` | 否 | 站点信息、是否开放会员中心、未登录可用规则；已登录时附带 `userInfo`、`menus`、`rules`。`requiredLogin=1` 且未登录则 303 |
| GET | `/api/user/checkIn` | 否 | 返回登录验证码开关、账户验证方式 |
| POST | `/api/user/checkIn` | 否 | `tab=login` 登录，`tab=register` 注册。成功返回 `userInfo`、`routePath=/user` |
| POST | `/api/user/logout` | 否 | 参数 `refreshToken` |
| GET | `/api/account/profile` | 是 | 返回账户验证方式 |
| POST | `/api/account/profile` | 是 | 更新资料 |
| POST | `/api/account/verification` | 是，免权限节点 | 校验当前邮箱或手机验证码，返回 `accountVerificationToken` |
| POST | `/api/account/changeBind` | 是，免权限节点 | 改绑邮箱或手机 |
| POST | `/api/account/changePassword` | 是 | 修改密码并退出 |
| POST | `/api/account/retrievePassword` | 否 | 找回密码。参数：`type`、`account`、`captcha`、`password` |
| GET | `/api/account/overview` | 是 | 近 7 日余额、积分 |
| GET | `/api/account/balance` | 是 | 余额流水 |
| GET | `/api/account/integral` | 是 | 积分流水 |

---

## 6. 常规管理

### 6.1 系统配置

#### 业务描述

以分组表单管理系统级变量，如站点名称、时区、禁访 IP、SMTP、后台入口和配置快捷入口。配置项本身也可增删。

#### 业务规则

- 变量名 `name` 全局唯一。分组来自配置项 `config_group`（数组，元素为 `key` / `value`）。
- 内置分组：`basics` 基础、`mail` 邮件、`config_quick_entrance` 快捷入口。
- 输入类型 `type` 决定后台表单组件（字符串、多行文本、下拉、数组、编辑器等）。`content` 存字典，`rule` 存校验规则，`extend` 存扩展属性。
- `allow_del = 0` 的项不允许删除。
- 富文本类型配置在保存时做 XSS 清理。
- 修改 `backend_entrance` 时：新值必须匹配 `^/[a-zA-Z0-9]+$`；同步改写前端后台路由常量、`config/app.php` 的应用映射，并在 `public/` 生成或删除对应入口 PHP 文件。改为 `/admin` 时不保留额外入口文件。
- 可发送测试邮件，依赖 SMTP 配置完整。
- 站点名、版本号、备案号、时区、禁访 IP 在请求初始化时生效。

内置配置项：

| name | 分组 | 说明 |
| --- | --- | --- |
| config_group | basics | 配置分组定义 |
| site_name | basics | 站点名称 |
| record_number | basics | 备案号 |
| version | basics | 对外版本号 |
| time_zone | basics | 时区，默认 `Asia/Shanghai` |
| no_access_ip | basics | 禁止访问的 IP，一行一个 |
| smtp_server / smtp_port / smtp_user / smtp_pass | mail | SMTP 服务器、端口、账号、密码 |
| smtp_verification | mail | `SSL` 或 `TLS` |
| smtp_sender_mail | mail | 发件邮箱 |
| config_quick_entrance | config_quick_entrance | 配置页快捷入口 |

#### 数据模型

**config 系统配置表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | ID |
| name | varchar(30) unique | 变量名 |
| group | varchar(30) | 分组 key |
| title | varchar(50) | 标题 |
| tip | varchar(100) | 描述 |
| type | varchar(30) | 输入组件类型 |
| value | longtext | 变量值 |
| content | longtext | 字典数据 |
| rule | varchar(100) | 验证规则 |
| extend | varchar(255) | 扩展属性 |
| allow_del | tinyint unsigned | `0` 不可删，`1` 可删 |
| weigh | int | 权重，越大越靠前 |

#### API 接口

控制器：`/admin/routine.Config/`。

| 方法 | 动作 | 说明 |
| --- | --- | --- |
| GET | `index` | 按分组返回配置项、分组标题、快捷入口 |
| POST | `edit` | 按变量名批量更新当前页配置 |
| POST | `add` | 新增配置项 |
| `del` | `del` | 删除允许删除的配置项 |
| POST | `sendTestMail` | 按当前 SMTP 配置发测试邮件 |

### 6.2 附件

#### 业务描述

管理员和会员上传文件后，系统保存物理文件并写入附件记录。后台可检索、编辑元数据和删除附件。

#### 业务规则

- 默认存储驱动 `local`。保存路径：`/storage/{topic}/{年月日}/{文件名前 15 字}{sha1}.{后缀}`。
- 单文件最大 10MB。后缀白名单：`jpg,png,bmp,jpeg,gif,webp,zip,rar,wav,mp4,mp3`。不允许可执行或配置文件。
- 同一 `sha1` 的重复上传增加 `quote` 并更新 `last_upload_time`，不重复落盘。
- 图片记录宽高。`topic` 用于业务分类，默认 `default`。
- 后台上传记 `admin_id`，会员上传记 `user_id`。
- 编辑时不允许改 `topic`、`url`、`storage`、`sha1`。
- 删除记录时同时删除物理文件。默认按最后上传时间倒序。
- 快速搜索：原始文件名。

#### 数据模型

**attachment 附件表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | ID |
| topic | varchar(20) | 细目 / 分类 |
| admin_id | int unsigned | 上传管理员，0 表示非管理员 |
| user_id | int unsigned | 上传会员，0 表示非会员 |
| url | varchar(255) | 物理路径 |
| width / height | int unsigned | 图片宽高，非图片为 0 |
| name | varchar(120) | 原始文件名 |
| size | int unsigned | 字节大小 |
| mimetype | varchar(100) | MIME |
| quote | int unsigned | 引用次数 |
| storage | varchar(50) | 存储方式 |
| sha1 | varchar(40) | 文件 SHA1 |
| create_time | bigint unsigned | 首次创建时间 |
| last_upload_time | bigint unsigned | 最后上传时间 |

#### API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/admin/ajax/upload` | 后台上传。表单字段 `file`，可选 `driver`、`topic`。需登录，免权限节点 |
| POST | `/api/ajax/upload` | 会员上传。需登录 |
| GET | `/admin/routine.Attachment/index` | 附件列表，关联上传人 |
| POST | `/admin/routine.Attachment/edit` | 编辑允许修改的元数据 |
| `del` | `/admin/routine.Attachment/del` | 删除记录和文件 |

### 6.3 个人资料

#### 业务描述

当前管理员查看并修改自己的头像、昵称、邮箱、手机、签名和密码，不能改用户名和状态。

#### 业务规则

- 只允许操作当前登录管理员。
- 只改头像时单独保存并返回成功。
- 修改密码使用重置密码，不回显原密码。
- 资料字段白名单：`id`、`username`、`nickname`、`avatar`、`email`、`mobile`、`motto`、`last_login_time`。

#### 数据模型

使用 `admin` 表。

#### API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/routine.AdminInfo/index` | 当前管理员资料 |
| POST | `/admin/routine.AdminInfo/edit` | 更新资料或密码 |

---

## 7. 数据安全

数据安全在后台写操作上自动生效：删除命中回收规则时把整行快照进回收站；编辑命中敏感字段规则时按字段记录修改前后值。规则按「控制器路径」匹配，一条控制器只对应一条规则。

### 7.1 数据回收

#### 业务描述

为指定后台控制器配置回收规则。该控制器执行删除时，删除前的行数据写入回收日志，之后可还原。

#### 业务规则

- 规则字段：名称、控制器、数据表、主键、数据库连接标识、状态。控制器在库内唯一。
- 保存时把控制器类名规范成小写斜杠路径，写入 `controller_as`，与请求的 `controllerPath` 比对。
- 仅 `status = 1` 且动作为 `del` 的 POST/DELETE 触发。按主键取出待删行，JSON 保存整行。
- 还原时按快照 `insert` 回原表（含原连接），成功后删除这条回收日志。
- 回收失败只记警告日志，不阻断原删除。
- 日志记录操作管理员、IP、User-Agent。

#### 数据模型

**security_data_recycle 回收规则表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 规则 ID |
| name | varchar(50) | 规则名称 |
| controller | varchar(100) | 控制器，唯一 |
| controller_as | varchar(100) | 规范化后的控制器路径 |
| data_table | varchar(100) | 数据表名 |
| connection | varchar(100) | 数据库连接标识，空为默认库 |
| primary_key | varchar(50) | 主键字段 |
| status | tinyint | `0` 禁用，`1` 启用 |
| update_time / create_time | bigint unsigned | 更新 / 创建时间 |

**security_data_recycle_log 数据回收记录表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 日志 ID |
| admin_id | int unsigned | 操作管理员 |
| recycle_id | int unsigned | 规则 ID |
| data | text | 被删行的 JSON |
| connection | varchar(100) | 数据库连接 |
| data_table | varchar(100) | 数据表 |
| primary_key | varchar(50) | 主键字段 |
| is_restore | tinyint unsigned | 历史字段。当前还原成功后直接删除日志 |
| ip | varchar(50) | 操作 IP |
| useragent | varchar(255) | User-Agent |
| create_time | bigint unsigned | 创建时间 |

#### API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/admin/security.DataRecycle/index` `add` `edit` `del` | 规则 CRUD。`add` 的 GET 返回可选控制器列表 |
| GET | `/admin/security.DataRecycleLog/index` | 回收日志，关联规则和管理员。快速搜索规则名 |
| GET | `/admin/security.DataRecycleLog/info` | 日志详情，解析 JSON 字段 |
| POST | `/admin/security.DataRecycleLog/restore` | 按 `ids` 还原 |

### 7.2 敏感数据

#### 业务描述

为指定控制器的若干字段建立监控。管理员修改这些字段时，记录修改前后的值，并支持回滚到修改前。

#### 业务规则

- 规则必填：名称、控制器（唯一）、数据表、主键、敏感字段映射 `data_fields`（字段名 => 中文名）。
- 仅 `status = 1` 且动作为 `edit` 的 POST 触发。
- 只记录「旧值与新提交值都存在且不相等」的字段。每个字段一条日志。
- 字段名包含 `password` 时：新值为空则忽略；新值非空则「修改后」记为 `******`，不落明文。
- 回滚把该字段更新为 `before`，成功后删除日志。
- 列表把主键值展示为 `主键名=值`。

#### 数据模型

**security_sensitive_data 敏感数据规则表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 规则 ID |
| name | varchar(50) | 规则名称 |
| controller / controller_as | varchar(100) | 控制器及规范化路径 |
| data_table | varchar(100) | 数据表 |
| connection | varchar(100) | 数据库连接 |
| primary_key | varchar(50) | 主键 |
| data_fields | text | 敏感字段 JSON |
| status | tinyint | `0` 禁用，`1` 启用 |
| update_time / create_time | bigint unsigned | 更新 / 创建时间 |

**security_sensitive_data_log 敏感数据修改记录**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | 日志 ID |
| admin_id | int unsigned | 操作管理员 |
| sensitive_id | int unsigned | 规则 ID |
| connection | varchar(100) | 数据库连接 |
| data_table | varchar(100) | 数据表 |
| primary_key | varchar(50) | 主键名 |
| data_field | varchar(50) | 被修改字段 |
| data_comment | varchar(50) | 字段中文名 |
| id_value | int | 被修改行的主键值 |
| before / after | text | 修改前 / 修改后 |
| ip / useragent | varchar | 操作者 IP 与 UA |
| is_rollback | tinyint unsigned | 历史字段。当前回滚成功后直接删除日志 |
| create_time | bigint unsigned | 创建时间 |

#### API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/admin/security.SensitiveData/index` `add` `edit` `del` | 规则 CRUD |
| GET | `/admin/security.SensitiveDataLog/index` | 修改日志 |
| GET | `/admin/security.SensitiveDataLog/info` | 单条对比 |
| POST | `/admin/security.SensitiveDataLog/rollback` | 按 `ids` 回滚字段 |

---

## 8. CRUD 代码生成

### 8.1 业务描述

开发者在后台用可视化设计器描述数据表和字段，系统生成控制器、模型、验证器、后台表格页、表单页和中英语言包，并写入菜单权限。也可以从已有表反推设计，或从历史记录再次生成、删除生成物。

`test_build` 是安装时自带的知识库示例表（标题、关键词、内容、浏览量、有帮助 / 无帮助、状态、权重），用于演示生成结果，不是独立产品模块。

### 8.2 业务规则

- 设计来源：从零新建、从已有数据表、从 AI 辅助设计。AI 接口为流式输出。
- 生成类型 `type=create` 或表设计 `rebuild=Yes` 时，先删除同名数据表再按设计重建。
- 生成物默认包括：后台控制器、模型、验证器、`web/src/views/backend/.../index.vue` 与 `popupForm.vue`、中英语言包，以及 `admin_rule` 菜单和按钮节点。
- 模型可生成到 `app/admin/model` 或 `app/common/model`。
- 支持选择数据库连接。表需有主键。快速搜索字段自动包含主键。
- 生成开始时写 `crud_log`，状态从 `start` 变为 `success`、`error` 或 `delete`。
- 日志可同步到 BuildAdmin 云端（可选）。删除生成记录时按日志清理已生成文件与菜单。
- 生成结束后通过内置 WEB 终端对前端文件执行 Prettier。
- 字段设计支持关联表、表单组件、列表渲染器、排序和拖拽权重。
- `logStart`、`getFileData`、`parseFieldData`、`generateCheck`、`uploadCompleted`、`aiConfig`、`aiStream` 免单独权限节点，但调用者仍需已登录。CRUD 日志列表要求具备 `crud/crud/index` 权限。

#### 日志状态

| 状态 | 含义 |
| --- | --- |
| start | 生成中 |
| success | 成功 |
| error | 失败 |
| delete | 已删除生成物 |

### 8.3 数据模型

**crud_log CRUD 记录表**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int unsigned PK | ID |
| table_name | varchar(200) | 数据表名 |
| comment | varchar(255) | 表注释 |
| table | text | 表设计 JSON |
| fields | text | 字段设计 JSON |
| sync | int unsigned | 是否已同步云端记录 |
| status | enum | `start` / `success` / `error` / `delete` |
| connection | varchar(100) | 数据库连接标识 |
| create_time | bigint unsigned | 创建时间 |

### 8.4 API 接口

控制器：`/admin/crud.Crud/`、`/admin/crud.Log/`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/admin/crud.Crud/generate` | 按 `type`、`table`、`fields` 生成代码和表 |
| POST | `/admin/crud.Crud/generateCheck` | 生成前检查表、文件是否冲突 |
| POST | `/admin/crud.Crud/logStart` | 记录一次生成开始 |
| POST | `/admin/crud.Crud/parseFieldData` | 解析字段设计 |
| GET | `/admin/crud.Crud/getFileData` | 读取已有表或历史设计 |
| POST | `/admin/crud.Crud/delete` | 按日志删除生成物 |
| GET | `/admin/crud.Crud/checkCrudLog` | 检查云端日志状态 |
| POST | `/admin/crud.Crud/uploadCompleted` | 标记云端同步完成 |
| GET | `/admin/crud.Crud/aiConfig` | AI 设计配置 |
| GET | `/admin/crud.Crud/aiStream` | AI 设计流式输出 |
| GET | `/admin/crud.Log/index` | 本地生成记录 |

配合的库表反射接口见「公共能力」中的后台 Ajax。云端日志地址为官方 `api.buildadmin.com` 的 `/api/v6.Crud/*`，不属于本仓库实现。

---

## 9. 模块市场

### 9.1 业务描述

管理员浏览已安装模块，从 BuildAdmin 模块市场安装、更新、启用、禁用、卸载模块，或上传本地模块包安装。安装过程通过内置终端拉取 Composer / 前端依赖。

### 9.2 业务规则

- 模块以 `uid` 标识，安装文件位于 `modules/{uid}`。
- 在线安装必须先登录 BuildAdmin 官网账号，并携带官网 token。付费模块需完成下单与支付确认后再下载。
- 安装状态由 `state` 轮询：下载、依赖安装、冲突确认、完成。
- 纯净安装（`module_pure_install`，默认开启）安装时移动模块文件而不是复制。
- 文件冲突时需管理员确认覆盖策略后才能继续。
- 启用、禁用会检查依赖模块是否允许变更。
- 卸载前应满足依赖检查。禁用或卸载失败时返回模块异常数据。
- 安装、改状态、卸载、上传安装都会写管理员日志。
- `state` 与 `dependentInstallComplete` 免单独权限节点。
- 模块列表接口同时返回当前系统版本和 Nuxt 端版本。

### 9.3 数据模型

模块元数据存放在各模块目录，不使用独立业务表。订单与支付由官网接口处理。

### 9.4 API 接口

本系统接口前缀：`/admin/module/`。市场接口前缀：`{api_url}/api/v7.store/`，`api_url` 默认 `https://api.buildadmin.com`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/module/index` | 已安装模块、系统版本、Nuxt 版本 |
| GET | `/admin/module/state` | 参数 `uid`，返回安装状态 |
| POST | `/admin/module/install` | 参数 `uid`、`token`、`update` |
| GET | `/admin/module/dependentInstallComplete` | 依赖安装完成后的收尾 |
| POST | `/admin/module/changeState` | 参数 `uid`、`state`，启用或禁用 |
| GET | `/admin/module/uninstall` | 参数 `uid` |
| GET | `/admin/module/upload` | 参数 `file`，从已上传包安装 |
| GET | `{api}/api/v7.store/modules` | 市场模块列表 |
| GET | `{api}/api/v7.store/info` | 模块详情 |
| POST | `{api}/api/v7.store/order` | 创建订单 |
| POST | `{api}/api/v7.store/pay` | 支付 |
| GET | `{api}/api/pay/check` | 支付结果 |
| POST | `{api}/api/v7.store/preDownload` | 下载前校验 |

---

## 10. 公共能力

### 10.1 业务描述

验证码、Token、地区、上传辅助、缓存清理和 WEB 终端供后台与会员端共用。邮件验证码用于注册、改绑、找回密码和账户验证。

### 10.2 业务规则

**Token（token 表）**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| token | varchar(50) PK | Token 字符串 |
| type | varchar(15) | `admin`、`admin-refresh`、`user`、`user-refresh`，以及 `email-pass`、`mobile-pass` |
| user_id | int unsigned | 管理员或会员 ID |
| create_time / expire_time | bigint unsigned | 创建与过期时间 |

- 默认驱动为 MySQL，可切换 Redis。过期 Token 由驱动清理。
- 刷新接口不主动删除旧访问 Token。刷新 Token 过期则要求重新登录。
- 账户验证通过后的 pass Token 有效期 600 秒，改绑成功后删除。

**验证码（captcha 表）**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| key | varchar(32) PK | 验证码键，通常为「账号 + 事件」 |
| code | varchar(32) | 加密后的验证码 |
| captcha | text | 点选验证码数据 |
| create_time / expire_time | bigint unsigned | 创建与过期时间 |

- 图形验证码 4 位数字。点选验证码长度 2，混淆点 2，模式为文字或图标。
- 邮件验证码同一邮箱同一事件 60 秒内不可重发。
- 邮件事件白名单：`user_register`、`user_change_email`、`user_retrieve_pwd`、`user_email_verify`。
- 注册时邮箱已被占用、改绑时新邮箱已被占用、找回或验证时邮箱未注册，均拒绝发送。
- `user_email_verify` 必须已登录、邮箱等于当前账号邮箱，并校验登录密码。
- 未配置 SMTP 时邮件服务不可用。

**地区（area 表）**

省市区三级字典：`pid`、`shortname`、`name`、`mergename`、`level`（1 省 / 2 市 / 3 区县）、`pinyin`、`code`、`zip`、`first`、`lng`、`lat`。接口按父级返回子级，供表单级联选择。

**其他**

- 清理缓存只影响后台运行时缓存，需登录。
- WEB 终端可调用本机命令，仅应在本地开发环境使用。`terminal` 动作免登录是为了安装阶段调用，生产环境需自行限制暴露面。
- 数据库连接列表、表列表、主键和字段列表供 CRUD 与安全规则选择表结构，返回前对连接信息脱敏。
- 按后缀生成的文件图标 SVG 可匿名获取。

### 10.3 API 接口

| 方法 | 路径 | 登录 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/common/captcha` | 否 | 图形验证码，参数 `id` |
| GET | `/api/common/clickCaptcha` | 否 | 创建点选验证码，参数 `id` |
| POST | `/api/common/checkClickCaptcha` | 否 | 校验点选验证码。参数 `id`、`info`、`unset` |
| POST | `/api/common/refreshToken` | 否 | 用 `refreshToken` 换新的访问 Token |
| POST | `/api/ems/send` | 按事件 | 发送邮件验证码。参数 `email`、`event`、`captchaId`、`captchaInfo`，账户验证另需 `password` |
| GET | `/admin/ajax/area` | 是 | 省市区 |
| GET | `/api/ajax/area` | 否 | 省市区 |
| GET | `/admin/ajax/buildSuffixSvg` | 是 | 文件后缀图标 |
| GET | `/api/ajax/buildSuffixSvg` | 否 | 文件后缀图标 |
| GET | `/admin/ajax/getDatabaseConnectionList` | 是 | 脱敏后的数据库连接 |
| GET | `/admin/ajax/getTableList` | 是 | 表列表 |
| GET | `/admin/ajax/getTablePk` | 是 | 表主键 |
| GET | `/admin/ajax/getTableFieldList` | 是 | 表字段 |
| POST | `/admin/ajax/clearCache` | 是 | 清理缓存 |
| POST | `/admin/ajax/changeTerminalConfig` | 是 | 修改终端配置（包管理器等） |
| POST | `/admin/ajax/terminal` | 安装场景免登录 | 执行终端命令 |

---

## 11. 安装器

### 11.1 业务描述

首次部署时，安装器检查 PHP 与前端环境、测试数据库、写入站点与管理员基础配置、执行迁移，并可通过终端安装依赖、发布前端构建产物。安装完成后安装器应不可再次进入。

### 11.2 业务规则

- 环境检查覆盖 PHP 版本、扩展、目录权限，以及 npm / pnpm 是否可用。
- 可切换前端包管理器。
- 数据库连接必须测试通过后才能写入基础配置。
- 基础配置包含数据库、站点和管理员初始账号。
- 命令执行结束、手动安装完成、移动 `web/dist` 到 `public/` 是三个独立收尾步骤。

### 11.3 数据模型

安装过程创建本文其余各表，并写入初始管理员（ID 1，角色组 1，`rules = *`）、默认配置和默认菜单。

### 11.4 API 接口

控制器：`/api/install/`（安装锁存在后不可用）。

| 动作 | 说明 |
| --- | --- |
| `terminal` | 安装期执行命令 |
| `changePackageManager` | 切换 npm / pnpm |
| `envBaseCheck` | PHP 与目录环境检查 |
| `envNpmCheck` | 前端包管理器检查 |
| `testDatabase` | 测试数据库连接 |
| `baseConfig` | 写入基础配置并安装 |
| `commandExecComplete` | 标记命令执行完成 |
| `manualInstall` | 手动安装收尾 |
| `mvDist` | 将前端构建产物移动到 `public/` |

---

## 12. 模块关系

```text
管理员 ──多对多── 角色组 ──引用── 后台菜单规则
   │                              │
   ├── 产生 管理员日志             └── 鉴权键 = 控制器/动作
   ├── 上传 附件
   └── 触发 数据回收 / 敏感字段日志

会员 ──属于── 会员组 ──引用── 会员菜单规则
  ├── 余额流水（写入时改余额）
  ├── 积分流水（写入时改积分）
  └── 上传 附件

系统配置 ──提供── 站点名、邮件、后台入口、禁访 IP
CRUD 日志 ──记录── 生成的表、代码和菜单
模块目录 ──独立于── 上述业务表
```

余额与积分的唯一入账入口是对应流水表。权限的唯一来源是规则表：后台看 `admin_rule`，会员看 `user_rule`。数据回收和敏感字段不改原业务表结构，只按控制器路径旁路记录。
