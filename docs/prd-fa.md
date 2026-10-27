# FastAdmin 产品需求文档（PRD）

> 整理日期：2026-10-27。本文根据当前仓库的控制器、模型、页面、配置和安装 SQL 反向整理，描述现有产品能力，并单独标注依赖、实现差异和待确认事项。本文未连接业务数据库，也未进行接口运行验证，不将代码存在等同于部署后已可用。

## 1. 产品概述

### 1.1 产品定位与目标

FastAdmin 是基于 ThinkPHP、Bootstrap 和 AdminLTE 的通用后台开发框架，为业务系统提供管理员权限、会员体系、附件管理、分类、配置、插件扩展和开发工具。当前仓库没有订单、商品、支付、CRM 等垂直业务实现；README 中提到的第三方业务应用属于可安装的扩展能力。

产品目标：

- 让管理员通过统一后台完成账号、权限、会员及基础数据管理。
- 为 Web 会员中心和 API 客户端提供共用的会员账号与认证能力。
- 通过配置、插件和 CRUD 生成器降低业务系统的搭建成本。
- 记录后台操作和会员余额、积分变更，支持管理追溯。

### 1.2 使用角色

| 角色 | 主要职责与边界 |
| --- | --- |
| 游客 | 访问首页、登录、注册、验证码及公开初始化接口 |
| 会员 | 登录会员中心、维护个人资料、修改密码、使用自己的附件 |
| 普通管理员 | 按授权访问后台模块，管理允许范围内的管理员和业务数据 |
| 超级管理员 | 拥有全部后台规则权限，可管理菜单规则和执行受限插件操作 |
| 开发与运维人员 | 初始化系统、生成业务代码和 API 文档、构建资源、管理扩展 |

管理员账号与会员账号分别存储在 `admin`、`user` 表中，是两套身份；Web 会员中心与 API 共用 `user` 会员体系。超级管理员由角色规则包含 `*` 判断，不应仅以某个固定账号名判断。

### 1.3 模块目录

| 编号 | 模块 | 主要入口 |
| --- | --- | --- |
| M01 | 后台登录与个人资料 | 后台登录、后台首页、个人配置 |
| M02 | 管理员与角色组 | 权限管理 → 管理员、角色组 |
| M03 | 后台菜单与权限规则 | 权限管理 → 菜单规则 |
| M04 | 管理员操作日志 | 权限管理 → 管理员日志 |
| M05 | 会员注册、登录与个人中心 | 前台会员中心、会员 API |
| M06 | 后台会员、会员组与会员权限 | 会员管理、会员分组、会员规则 |
| M07 | 会员余额、积分与等级 | 会员编辑、公共模型方法 |
| M08 | 短信与邮箱验证码 | 短信、邮件及表单验证 API |
| M09 | 文件上传与附件管理 | 附件管理、附件选择器、上传 API |
| M10 | 分类与地区字典 | 分类管理、分类及省市区联动 |
| M11 | 系统配置 | 常规管理 → 系统配置 |
| M12 | 控制台与统计 | 后台控制台 |
| M13 | 插件管理 | 插件管理 |
| M14 | 公共接口与系统辅助能力 | 初始化、Token、语言包、缓存、排序 |
| M15 | 系统安装与开发工具 | Web 安装入口、命令行工具 |

## 2. 全局业务与接口约定

### 2.1 路径与调用方式

为避免部署入口差异，本文采用以下路径记号：

| 记号 | 含义 | 示例 |
| --- | --- | --- |
| `{ADMIN}` | 绑定 admin 模块的后台入口及路径前缀 | 安装前源码为 `/admin.php`，安装程序会将其改为随机名称；如 `/{随机入口}.php/auth/admin/index` |
| `{WEB}` | 前台 index 模块前缀 | 使用重写时可为 `/index`，如 `/index/user/login` |
| `{API}` | API 模块前缀 | 使用重写时为 `/api`，如 `/api/user/login` |

API 未开启 URL 重写时可经 `/index.php/api/...` 访问；前台页面还可能包含 `.html` 后缀。实际地址应由项目 URL 生成方法和部署配置确定，不能将后台入口固定为 `/admin/...`。

接口表中的 GET、POST 描述页面及客户端的调用约定。部分控制器只读取 POST 参数，没有显式拦截其他 HTTP 方法，不能视为已经实现严格的 REST 方法约束。文件上传使用 `multipart/form-data`；普通表单通常使用表单编码。本文只列业务入口，不把初始化方法、继承方法全部当作可用产品功能。

### 2.2 认证与权限

- **后台认证**：基于管理员 Session；页面及后台 AJAX 请求携带会话 Cookie。会员 Token 不能代替管理员登录。
- **会员认证**：API 依次从请求头 `token`、请求参数 `token`、Cookie `token` 读取凭证；Web 会员中心也使用会员 Token。
- **后台授权**：通常以 `控制器/方法` 对应权限规则；菜单根据已授权规则生成。
- **会员授权**：需要鉴权的入口以 `模块/控制器/方法` 对应会员规则，例如 `api/demo/test3`。
- **权限例外**：`noNeedLogin` 表示跳过强制登录及规则鉴权；`noNeedRight` 表示仍需登录，但跳过该入口的规则鉴权。方法内仍可能补充权限检查。
- **数据范围**：后台基类支持 `auth`（按管理员权限范围）与 `personal`（仅本人）两种限制，默认关闭；不是所有表自动按管理员隔离。管理员管理、操作日志、会员附件等另有显式范围约束。
- **表单令牌**：调用了 `token()` 或表单 Token 验证的入口需要提交 `__token__`。该防重复/跨站请求令牌与会员登录 Token 是不同字段和用途，不能混用；不能假定所有写接口都有同样校验。

### 2.3 响应格式

API 基类统一返回：

```json
{
  "code": 1,
  "msg": "操作成功",
  "time": 1793059200,
  "data": null
}
```

| 字段/场景 | 说明 |
| --- | --- |
| `code=1` | 默认业务成功 |
| `code=0` | 默认业务失败，具体原因见 `msg` |
| `code=401` | 需要登录或凭证无效，通常同时返回 HTTP 401 |
| `code=403` | 没有规则权限，通常同时返回 HTTP 403 |
| `time` | 服务端本次请求时间，Unix 秒级时间戳 |
| `data` | 业务数据，无数据时通常为 `null` |

普通业务失败通常仍返回 HTTP 200，客户端需要判断业务 `code`。上述封装适用于 `Api` 基类的业务返回；验证码图片、SVG、语言包、异常处理及直接返回 JSON 的接口有各自格式。

后台常用列表返回 `{"total": 总数, "rows": [...]}`；SelectPage 通常返回 `list`、`total`；后台表单操作沿用 ThinkPHP 的页面/AJAX 跳转响应，常见字段为 `code/msg/data/url/wait`，不能直接套用 API 响应结构。

### 2.4 查询与数据约定

| 参数/约定 | 含义 |
| --- | --- |
| `search` | 快速搜索，搜索字段由各控制器确定 |
| `filter` | JSON 字符串，指定字段筛选值 |
| `op` | JSON 字符串，指定对应筛选操作符 |
| `sort/order` | 排序字段及 `asc/desc` |
| `offset/limit` | 列表偏移量与页大小；也可由 `page` 指定页码 |
| `keyField/keyValue/showField` | SelectPage 的主键、回显值和展示字段等参数 |
| `row[...]` | 后台新增、编辑表单的业务字段集合 |
| `ids` | 目标主键；部分接口支持逗号分隔多个 ID，具体见模块说明 |
| `params` | 通用批量更新的 URL 编码字段串，例如 `status=hidden` |

数据表在文中省略配置前缀，安装 SQL 的默认前缀为 `fa_`。`createtime/updatetime` 等字段通常为 Unix 秒级时间戳；生日为 `date`；金额使用两位小数。下文数据模型按业务分组列出关键字段及约束，完整数据库类型以安装 SQL 为准。模型关系通常由代码维护，不能理解为数据库已经配置外键约束。

## 3. M01 后台登录与个人资料

### 3.1 业务描述

管理员通过账号密码进入后台，获得根据权限生成的菜单；可保持登录、退出登录，并维护自己的邮箱、昵称、头像和密码。

### 3.2 业务规则

1. 登录账号为管理员用户名；登录页面要求用户名和密码长度均为 3～30 位，新增/重设管理员密码则要求 6～30 位非空白字符，两处规则并不完全一致。
2. 登录提交必须包含有效 `__token__`；默认开启图形验证码校验。
3. `hidden` 状态管理员不能登录。默认启用失败次数限制：失败达到 10 次后，若距管理员 `updatetime` 不足 24 小时则拒绝继续尝试。
4. 登录成功重置失败次数，更新登录时间、IP 与 Session 标识，并重新生成 Session ID。
5. 勾选保持登录时，后台登录控制器设置 24 小时的自动登录凭证。
6. 默认开启登录 IP 变化检查；单账号唯一登录开关默认关闭。关键账号信息安全码不匹配时要求重新登录。
7. 退出操作实际由 POST 执行，校验表单 Token；Referer 存在时必须与当前主机一致。
8. 修改个人信息只接收 `email/nickname/password/avatar`；邮箱需要格式正确且未被其他管理员使用，密码留空表示不修改。资料保存后同步更新当前 Session。

### 3.3 业务流程

访问登录页 → 获取表单令牌与验证码 → 提交账号密码 → 验证账号状态、失败次数和密码 → 建立 Session → 加载授权菜单 → 进入固定首页。

### 3.4 数据模型

| 实体 | 关键字段 | 约束与关系 |
| --- | --- | --- |
| `admin` | `id, username, nickname, email, mobile, avatar, status` | `id` 主键；数据库对 `username` 建唯一索引 |
| 管理员凭证 | `password varchar(32), salt, token` | 密码以 `md5(md5(明文)+salt)` 保存；`token` 为后台 Session 标识，不是会员 Token |
| 登录记录字段 | `loginfailure, logintime, loginip, createtime, updatetime` | 当前登录状态与失败次数 |
| 会话与 Cookie | `admin` Session、自动登录 Cookie | 与管理员记录共同决定当前会话是否有效 |

### 3.5 API 与页面接口

| 方法 | 路径 | 主要参数 | 权限与返回 |
| --- | --- | --- | --- |
| GET / POST | `{ADMIN}/index/login` | POST：`username*, password*, __token__*, captcha`，可选 `keeplogin`；GET 可带 `url` | 游客；GET 页面，POST 登录结果及管理员基本信息 |
| GET | `{ADMIN}/index/index` | 页面展示参数 | 管理员；后台框架页和授权菜单 |
| POST | `{ADMIN}/index/index` | `action=refreshmenu` | 管理员；`data.menulist/navlist` |
| GET / POST | `{ADMIN}/index/logout` | POST：`__token__` | 管理员；GET 确认页，POST 退出结果 |
| GET | `{ADMIN}/general/profile/index` | 列表查询参数 | 对应后台权限；页面或本人的操作日志列表 |
| POST | `{ADMIN}/general/profile/update` | `row[email]*, row[nickname], row[avatar], row[password], __token__` | 对应后台权限；保存结果 |

依据：`application/admin/controller/Index.php`、`application/admin/controller/general/Profile.php`、`application/admin/library/Auth.php`。

## 4. M02 管理员与角色组

### 4.1 业务描述

通过多角色和上下级角色组管理后台人员，允许有授权的管理员创建和维护其管理范围内的下级管理员、下级角色组，并分配权限。

### 4.2 业务规则

1. 一个管理员可加入多个角色组；角色组通过 `pid` 形成层级。
2. 管理员列表及编辑对象受当前操作者可管理的下级管理员集合约束；角色分配仅接受允许范围内的角色组，过滤后不能为空。
3. 创建管理员时同时保存账号和角色关联，任何一步失败均回滚；新管理员采用默认头像。
4. 编辑管理员时密码为空保持原密码；角色关联重新写入。
5. 删除管理员时不能删除当前操作者本人，同时删除角色关联；管理员的通用批量更新入口明确禁用。
6. 新建角色的权限取提交权限、父角色权限和操作者权限的交集；拥有 `*` 的一方不作该项限制。
7. 角色不能将自己或自己的子角色设为父角色。修改角色权限后，子角色权限会被收缩到新的权限集合内。
8. 当前管理员所在角色、有管理员的角色、有子角色的角色不能直接删除；角色通用批量更新入口明确禁用。

### 4.3 业务流程

创建下级角色 → 在允许的规则树中选择权限 → 创建管理员并选择角色 → 系统过滤越权分配 → 事务保存账号和关系 → 新管理员登录后获得相应菜单和操作能力。

### 4.4 数据模型

| 表 | 字段 | 关系与约束 |
| --- | --- | --- |
| `admin` | 见 M01 | 管理员主体 |
| `auth_group` | `id, pid, name, rules, status, createtime, updatetime` | `pid` 指向父角色；`rules` 存规则 ID 逗号串或 `*` |
| `auth_group_access` | `uid, group_id` | `uid → admin.id`，`group_id → auth_group.id`；`(uid,group_id)` 联合唯一；SQL 注释中的“会员ID”在此实际表示管理员 ID |

### 4.5 API 接口

以下均需管理员登录和对应操作权限。

| 方法 | 路径 | 主要参数 | 返回/作用 |
| --- | --- | --- | --- |
| GET | `{ADMIN}/auth/admin/index` | 通用列表参数 | 页面或管理员列表，包含角色 ID、角色名称，排除密码、盐和 Session 标识 |
| GET / POST | `{ADMIN}/auth/admin/add` | POST：`row[username/password/email/nickname/mobile/status]`、`group[]`、`__token__` | 新增页面/保存结果 |
| GET / POST | `{ADMIN}/auth/admin/edit` | `ids`、`row[...]`、`group[]`、POST `__token__` | 编辑页面/保存结果 |
| POST | `{ADMIN}/auth/admin/del` | `ids`，可多选 | 删除结果 |
| GET | `{ADMIN}/auth/admin/selectpage` | SelectPage 参数 | 范围受限的管理员下拉数据 |
| GET | `{ADMIN}/auth/group/index` | AJAX 标识 | 页面或角色树列表 |
| GET / POST | `{ADMIN}/auth/group/add` | `row[pid/name/rules/status]`，POST `__token__` | 新增页面/保存结果 |
| GET / POST | `{ADMIN}/auth/group/edit` | `ids`、`row[pid/name/rules/status]`，POST `__token__` | 编辑页面/保存结果 |
| POST | `{ADMIN}/auth/group/del` | `ids` | 按实际可删除条件处理 |
| POST | `{ADMIN}/auth/group/roletree` | `pid`，可选当前角色 `id` | 可选权限节点树；跳过入口规则鉴权，但仍受内部可分配范围过滤 |

依据：`application/admin/controller/auth/Admin.php`、`Group.php` 及 `application/admin/model/AuthGroupAccess.php`。

## 5. M03 后台菜单与权限规则

### 5.1 业务描述

超级管理员维护后台菜单结构及操作权限节点。一个规则可用于页面菜单展示，也可用于控制某个操作是否允许执行。

### 5.2 业务规则

1. 整个规则管理控制器仅允许超级管理员访问。
2. `name` 为规则标识，通常对应 `控制器/方法`，必须唯一；`title` 为显示名称。
3. 非菜单节点必须有父节点；父节点不能是自己或自己的后代。
4. `ismenu` 控制是否展示为菜单；菜单打开方式支持 `addtabs/blank/dialog/ajax`。
5. 规则支持状态、图标、URL、备注、权重和扩展属性；列表按权重组织为树。
6. 删除规则会同时删除其子节点，并清除菜单缓存。角色表中的规则 ID 是字符串引用，删除后的引用清理由后续维护决定。
7. 批量更新通常允许 `ismenu/status`；超级管理员在通用批量更新实现中拥有更宽的字段权限。

### 5.3 数据模型

| 表 | 字段组 | 说明 |
| --- | --- | --- |
| `auth_rule` | `id, pid, name, title` | 主键、父节点、唯一规则标识、展示标题 |
| `auth_rule` | `type, condition, remark` | 规则类型、条件及说明 |
| `auth_rule` | `ismenu, menutype, icon, url, extend` | 菜单展示与打开方式 |
| `auth_rule` | `py, pinyin, weigh, status, createtime, updatetime` | 搜索辅助字段、排序及状态 |

### 5.4 API 接口

| 方法 | 路径 | 参数 | 返回/作用 |
| --- | --- | --- | --- |
| GET | `{ADMIN}/auth/rule/index` | AJAX 标识 | 页面或规则树 `total/rows` |
| GET / POST | `{ADMIN}/auth/rule/add` | `row[pid/name/title/ismenu/menutype/icon/url/weigh/status/extend/remark]`，POST `__token__` | 新增页面/保存结果 |
| GET / POST | `{ADMIN}/auth/rule/edit` | `ids`、`row[...]`，POST `__token__` | 编辑页面/保存结果 |
| POST | `{ADMIN}/auth/rule/del` | `ids` | 删除节点及其后代 |
| POST | `{ADMIN}/auth/rule/multi` | `ids, params` | 通用批量更新结果 |

依据：`application/admin/controller/auth/Rule.php`、`application/admin/model/AuthRule.php`、`application/admin/validate/AuthRule.php`。

## 6. M04 管理员操作日志

### 6.1 业务描述

自动记录后台写操作的操作者、页面、内容、时间和来源，支持查询、查看详情和删除。

### 6.2 业务规则

1. 默认启用自动日志，仅记录后台 POST 请求；默认忽略以 `/selectpage`、`/index` 结尾的路径，因此不是完整的所有访问记录。
2. 日志标题可由代码显式设置；未设置时根据权限面包屑生成。
3. 默认内容来自请求参数或原始请求体；对数组内容递归屏蔽字段名包含 `password/salt/token` 的值。非数组原文不经过这项字段级替换。
4. 普通管理员只可查看、删除自身及允许范围内管理员的日志；超级管理员可查看全部。
5. 列表不返回 `content/useragent`，详情页展示完整日志；不允许人工新增、编辑和批量改写日志。
6. 当前没有保存期限、自动归档和不可篡改审计规则。

### 6.3 数据模型

| 表 | 字段 | 说明 |
| --- | --- | --- |
| `admin_log` | `id, admin_id, username` | 日志主键、操作者 ID 和用户名快照 |
| `admin_log` | `url varchar(1500), title, content longtext` | 操作位置、标题和内容 |
| `admin_log` | `ip, useragent, createtime` | 请求来源与时间 |

### 6.4 API 接口

| 方法 | 路径 | 参数 | 返回/权限 |
| --- | --- | --- | --- |
| GET | `{ADMIN}/auth/adminlog/index` | 通用查询参数 | 页面或范围内日志列表 |
| GET | `{ADMIN}/auth/adminlog/detail` | `ids` | 范围内日志详情页 |
| POST | `{ADMIN}/auth/adminlog/del` | `ids` | 范围内日志删除结果 |
| GET | `{ADMIN}/general/profile/index` | 通用查询参数、AJAX 标识 | 当前管理员本人的日志 |

依据：`application/admin/behavior/AdminLog.php`、`application/admin/model/AdminLog.php`、`application/admin/controller/auth/Adminlog.php`。

## 7. M05 会员注册、登录与个人中心

### 7.1 业务描述

向网站会员和 API 客户端提供账号注册、密码登录、短信登录、个人资料维护、联系方式验证、密码修改和密码找回。Web 与 API 共用账号，但入口校验规则有差异。

### 7.2 业务规则

1. 会员中心受 `fastadmin.usercenter` 控制，当前默认开启。
2. 密码登录支持用户名、邮箱或手机号；系统根据账号格式选择查询字段。
3. 会员必须为 `normal` 状态；密码失败累计达到 10 次且距最后失败不足 24 小时时拒绝密码登录。登录成功清零失败次数。
4. 注册时检查用户名及昵称占用；非空邮箱和手机号也检查占用。默认昵称取用户名，部分手机号形式用户名会脱敏。
5. API 注册实际要求非空 `username/password`，并验证 `mobile + code` 的 `register` 短信验证码；邮箱传入时校验格式。虽然控制器注释将邮箱、手机都标为必填，实际应按上述代码路径理解。
6. Web 注册要求用户名 3～30 位、密码 6～30 位、有效邮箱和表单令牌；手机号填写时校验格式。注册验证方式由配置决定，当前默认图形验证码，还可选短信、邮箱或微信插件验证码。
7. 短信登录使用 `mobilelogin` 事件验证码；号码未注册时自动创建会员，密码随机生成；已有会员会检查账号状态。
8. 注册/登录成功签发会员 Token，默认有效期 30 天；Web 登录可用 Cookie 保持登录，勾选时设置 30 天 Cookie 有效期。
9. 登录会更新 `prevtime/logintime/loginip` 和连续登录天数，同一天多次登录不重复增加天数。
10. API 资料修改支持用户名、昵称、头像和简介；用户名、昵称传入时检查其他会员占用，头像仅接受配置路径/CDN/主机前缀等允许形式。
11. 联系方式修改校验新手机号/邮箱唯一性及对应事件验证码，成功后更新 `verification.mobile/email`。这两个 API 当前被列入免登录白名单，却又直接使用当前会员对象，属于实现差异，见第 18 节。
12. 已登录修改密码需要校验旧密码；找回密码使用 `resetpwd` 手机或邮箱验证码。修改密码会删除当前认证实例持有的 Token；没有统一清除该会员所有其他 Token 的逻辑。
13. 第三方登录依赖 `third` 插件，当前 `addons/` 目录无实际插件，不能视为开箱即用。

### 7.3 业务流程

**注册**：选择注册入口 → 完成入口要求的验证码 → 校验账号及联系方式 → 创建会员 → 签发 Token → 进入个人中心。

**短信登录**：发送 `mobilelogin` 验证码 → 提交手机号与验证码 → 校验验证码 → 已有会员直接登录/无会员自动注册 → 返回 `userinfo`。

**找回密码**：发送 `resetpwd` 验证码 → 提交联系方式、验证码及新密码 → 查询会员并验证 → 以内部直接登录流程设置认证上下文 → 修改密码并删除该上下文的 Token → 返回重置结果。

### 7.4 数据模型

| 表/字段组 | 关键字段 | 说明 |
| --- | --- | --- |
| `user` 身份资料 | `id, group_id, username varchar(32), nickname varchar(50), email, mobile varchar(11), avatar, gender, birthday, bio` | `group_id → user_group.id`；性别当前后台映射 `1=男，0=女` |
| `user` 凭证状态 | `password varchar(32), salt, status, verification` | 密码加盐摘要；验证状态存 JSON 文本，读取时补充 `email/mobile` 默认 0 |
| `user` 活跃数据 | `jointime, joinip, prevtime, logintime, loginip, loginfailure, loginfailuretime, successions, maxsuccessions` | 注册、登录、失败与连续登录信息 |
| `user` 资产字段 | `money, score, level` | 详见 M07 |
| `user_token` | `token, user_id, createtime, expiretime` | 有效认证记录，详见 M14；`user.token` 字段不能替代此表 |

`user.username/email/mobile` 在安装 SQL 中仅为普通索引，代码执行占用检查；不能宣称数据库已强制唯一。注册代码没有显式设置 `group_id`，默认使用表字段值 0，业务若要求自动进入某组需另行配置或扩展。

### 7.5 API 接口

`*` 表示此入口业务路径需要的参数。登录成功的 `data.userinfo` 默认包含 `id/username/nickname/mobile/avatar/score`，并合并 Token 信息：`token/user_id/createtime/expiretime/expires_in`。

| 方法 | 路径 | 主要参数 | 登录要求与返回 |
| --- | --- | --- | --- |
| GET | `{API}/user/index` | Token | 需会员登录；`data.welcome` 为昵称 |
| POST | `{API}/user/login` | `account*, password*` | 公开；`data.userinfo` |
| POST | `{API}/user/mobilelogin` | `mobile*, captcha*` | 公开；`data.userinfo` |
| POST | `{API}/user/register` | `username*, password*, mobile*, code*`，可选 `email` | 公开；`data.userinfo`；手机必需性来自短信校验 |
| POST | `{API}/user/logout` | Token | 需会员登录，显式限制 POST；删除当前 Token |
| POST | `{API}/user/profile` | Token；`username, nickname, avatar, bio` | 需会员登录；保存结果；`bio` 会被本次值覆盖 |
| POST | `{API}/user/changeemail` | 有效会员上下文；`email*, captcha*` | 实际业务依赖登录，白名单存在差异；保存结果 |
| POST | `{API}/user/changemobile` | 有效会员上下文；`mobile*, captcha*` | 实际业务依赖登录，白名单存在差异；保存结果 |
| POST | `{API}/user/resetpwd` | `newpassword*, captcha*`；`type=mobile` 时 `mobile*`，其他分支使用 `email*` | 公开；重置结果；新密码要求 6～30 位非空白字符 |
| POST | `{API}/user/third` | `platform*, code*` | 公开、依赖插件；`data.userinfo/thirdinfo` |

### 7.6 Web 页面与交互

| 方法 | 路径 | 主要参数/行为 |
| --- | --- | --- |
| GET / POST | `{WEB}/user/register` | GET 注册页；POST `username/password/email/mobile/captcha/__token__`，可选跳转 `url` |
| GET / POST | `{WEB}/user/login` | GET 登录页；POST `account/password/__token__`，可选 `keeplogin/url` |
| GET | `{WEB}/user/index` | 会员中心页，需登录 |
| GET | `{WEB}/user/profile` | 个人资料页，资料保存调用会员 API |
| GET / POST | `{WEB}/user/changepwd` | POST `oldpassword/newpassword/renewpassword/__token__`，两次新密码需一致 |
| GET / POST | `{WEB}/user/logout` | POST 才执行退出，要求同源 Referer 和表单 Token；GET 确认页 |
| GET | `{WEB}/user/attachment` | 需登录；本人附件列表/选择页，见 M09 |

依据：`application/api/controller/User.php`、`application/index/controller/User.php`、`application/common/library/Auth.php`、`application/common/model/User.php`。

## 8. M06 后台会员、会员组与会员权限

### 8.1 业务描述

管理员查询及维护会员资料、状态、分组和资产，并通过会员组和会员规则为需要鉴权的前台/API 功能配置访问权限。

### 8.2 业务规则

1. 会员列表支持 ID、用户名、昵称搜索和关联会员组展示；不返回密码和盐，头像为空时生成字母头像。
2. 编辑会员可修改分组、用户名、昵称、邮箱、手机号、头像、等级、生日、简介、余额、积分和登录相关资料。
3. 编辑启用会员验证器，用户名、昵称和邮箱有必填/唯一等校验；手机号检查唯一；修改密码留空保持原值，有值时重新生成盐和摘要。
4. 删除会员通过会员 Auth 服务执行，同时清除该会员所有 Token 并触发删除钩子；没有统一删除附件、积分日志、余额日志等关联数据的代码。
5. 一个会员只有一个 `group_id`，与管理员多角色机制不同；会员组没有 `pid` 层级字段。
6. 会员组 `rules` 保存会员规则 ID；规则本身通过 `pid` 形成树，只有 `normal` 规则进入会员权限列表。
7. 会员规则删除时会删除后代规则；通用批量更新支持 `ismenu/status` 等约定。
8. 当前会员中心和大部分会员 API 配置为跳过规则鉴权；会员规则主要对主动要求鉴权的控制器生效，不能据此宣称全部 API 都按会员组隔离。
9. 后台会员新增方法存在，但仓库缺少对应新增视图，且后台会员模型只对更新处理密码；新增完整可用性需确认，不能等同于已完成后台开户流程。

### 8.3 数据模型

| 表 | 字段 | 关系与约束 |
| --- | --- | --- |
| `user` | 见 M05 | `group_id` 关联一个会员组 |
| `user_group` | `id, name, rules, status, createtime, updatetime` | 会员分组，无上下级结构 |
| `user_rule` | `id, pid, name, title, remark, ismenu, weigh, status, createtime, updatetime` | 规则名使用含模块的路径；父子关系通过 `pid` 表示 |

### 8.4 API 接口

以下均为后台管理接口，需要管理员及对应规则权限。

| 方法 | 路径 | 参数 | 返回/作用 |
| --- | --- | --- | --- |
| GET | `{ADMIN}/user/user/index` | 通用列表参数 | 页面/会员列表，包含 `group` |
| GET / POST | `{ADMIN}/user/user/edit` | `ids`、`row[会员字段]`，POST `__token__` | 编辑页面/保存结果 |
| POST | `{ADMIN}/user/user/del` | `ids` | 当前实现按单个会员读取与删除，不承诺批量删除 |
| POST | `{ADMIN}/user/user/multi` | `ids, params` | 通用批量更新，普通管理员默认仅允许状态 |
| GET | `{ADMIN}/user/group/index` | 通用列表参数 | 页面/分组列表 |
| GET / POST | `{ADMIN}/user/group/add`、`{ADMIN}/user/group/edit` | 编辑传 `ids`；`row[name/rules/status]`，POST `__token__` | 页面/保存结果 |
| POST | `{ADMIN}/user/group/del`、`{ADMIN}/user/group/multi` | `ids`，批量更新另传 `params` | 通用删除/更新；未见阻止删除被会员引用分组的专门逻辑 |
| GET | `{ADMIN}/user/rule/index` | AJAX 标识 | 页面/会员规则树 |
| GET / POST | `{ADMIN}/user/rule/add`、`{ADMIN}/user/rule/edit` | 编辑传 `ids`；`row[pid/name/title/remark/ismenu/weigh/status]`，POST `__token__` | 页面/保存结果 |
| POST | `{ADMIN}/user/rule/del`、`{ADMIN}/user/rule/multi` | `ids`，批量更新另传 `params` | 删除后代规则/批量更新 |

后台新增会员 `{ADMIN}/user/user/add` 仅作为现有代码入口记录，不作为已完整交付的可用功能，待确认项见第 18 节。

依据：`application/admin/controller/user/`、`application/admin/model/User.php`、`UserGroup.php`、`UserRule.php`、`application/admin/validate/User.php`。

## 9. M07 会员余额、积分与等级

### 9.1 业务描述

维护会员余额和积分，记录每次变化的前后值。框架提供内部增减方法和后台会员编辑联动日志，没有独立充值、提现、支付、积分商城或账单查询业务。

### 9.2 业务规则

1. 余额变动使用公共模型 `User::money(变动值, 会员ID, 备注)`，积分变动使用 `User::score(...)`。
2. 公共增减方法使用事务及会员行锁，变动非零且会员存在时更新账户并记录日志；异常时回滚。
3. 余额按两位小数处理，优先使用 BCMath；当前没有余额/积分不得为负、幂等业务单号等约束。
4. 调用公共积分方法会按积分自动计算等级；后台直接编辑积分仅触发变更日志，不会调用该自动等级计算逻辑，等级字段可独立维护。
5. 后台编辑余额和积分，模型会按新旧值差额写入日志，备注为“管理员变更金额/积分”。
6. 资产日志没有独立管理页面和对外查询 API；内部方法异常被捕获后不向调用方提供统一错误结果，调用方需自行确认业务处理。

| 等级 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 达到积分 | 0 | 30 | 100 | 500 | 1000 | 2000 | 3000 | 5000 | 8000 | 10000 |

### 9.3 业务流程

业务代码发起增减 → 锁定会员 → 读取当前值 → 计算变动后值及积分等级 → 更新会员 → 写入前值、后值、差额与备注 → 提交事务。

### 9.4 数据模型

| 表 | 字段 | 说明 |
| --- | --- | --- |
| `user` | `money decimal(10,2), score int, level` | 当前余额、积分、等级 |
| `user_money_log` | `id, user_id, money decimal(10,2), before, after, memo, createtime` | `money` 为本次差额，正负表示增加或扣减 |
| `user_score_log` | `id, user_id, score int, before, after, memo, createtime` | 积分变动记录 |

### 9.5 API 与内部服务

| 类型 | 入口 | 参数 | 权限/结果 |
| --- | --- | --- | --- |
| 后台 POST | `{ADMIN}/user/user/edit` | `ids`、`row[money/score/level]` 等、`__token__` | 需会员编辑权限；保存会员并触发日志 |
| 内部模型方法 | `app\common\model\User::money` | `$money, $user_id, $memo` | 供可信业务代码调用，无独立 HTTP API |
| 内部模型方法 | `app\common\model\User::score` | `$score, $user_id, $memo` | 更新积分及等级，无独立 HTTP API |
| 内部模型方法 | `app\common\model\User::nextlevel` | `$score` | 返回等级 |

依据：`application/common/model/User.php`、`MoneyLog.php`、`ScoreLog.php`、`application/admin/model/User.php`。

## 10. M08 短信与邮箱验证码

### 10.1 业务描述

为注册、短信登录、修改联系方式和找回密码提供验证码发送与校验，同时提供账号占用及存在性检查，用于表单即时反馈。

### 10.2 业务规则

1. 手机格式按 `^1\d{10}$` 验证；邮箱需格式有效。发送事件默认 `register`，邮件事件额外要求 3～30 位字母、数字、下划线或连字符。
2. 同一联系方式、同一事件两次发送间隔至少 60 秒；同一 IP 最近一小时已保存的验证码记录达到 5 条则拒绝发送。该计数基于当前记录，不是独立的永久发送流水。
3. 默认生成 6 位数字验证码，有效期 120 秒；最多校验 10 次，成功和失败都会增加次数。
4. 校验读取该联系方式和事件的最新记录，使用事务及行锁；支持成功后删除验证码。会员 API 的关键验证码校验传入删除标志，独立校验接口通常不消费验证码。
5. `register` 要求联系方式未注册；`changeemail/changemobile` 要求新联系方式未占用；`changepwd/resetpwd` 要求会员已存在；`mobilelogin` 允许未注册号码。
6. 短信发送依赖 `sms_send` 插件钩子，未安装时明确提示安装；邮箱未设置 `ems_send` 钩子时使用框架 SMTP 邮件发送。
7. 邮箱独立校验接口要求验证码为 4～6 位字母数字；短信独立校验最终由验证码库判断。
8. 占用检测是表单辅助功能，不代替提交时的最终业务校验。

### 10.3 业务流程

提交联系方式和事件 → 校验格式、账号状态与频率 → 生成并保存验证码 → 调用短信插件/邮件服务 → 用户提交验证码 → 锁定最新记录、校验时间/次数/内容 → 执行业务并按调用方式消费验证码。

### 10.4 数据模型

| 表 | 字段 | 状态 |
| --- | --- | --- |
| `sms` | `id, event, mobile, code, times, ip, createtime` | 安装 SQL 已提供；验证码及校验次数记录 |
| `ems` | `id, event, email varchar(100), code varchar(10), times, ip, createtime` | 安装 SQL 已提供；`id` 为主键，记录邮箱验证码及校验次数 |

### 10.5 API 接口

以下接口均公开，无强制登录；发送能力受依赖及业务校验约束。

| 方法 | 路径 | 主要参数 | 返回 |
| --- | --- | --- | --- |
| POST | `{API}/sms/send` | `mobile*`，可选 `event` | 发送结果 |
| POST | `{API}/sms/check` | `mobile*, captcha*`，可选 `event` | 校验结果 |
| POST | `{API}/ems/send` | `email*`，可选 `event` | 发送结果 |
| POST | `{API}/ems/check` | `email*, captcha*`，可选 `event` | 校验结果 |
| POST | `{API}/validate/check_username_available` | `username`，可选排除 `id` | 用户名是否可用 |
| POST | `{API}/validate/check_nickname_available` | `nickname`，可选排除 `id` | 昵称是否可用 |
| POST | `{API}/validate/check_email_available` | `email`，可选排除 `id` | 邮箱是否可用 |
| POST | `{API}/validate/check_mobile_available` | `mobile`，可选排除 `id` | 手机号是否可用 |
| POST | `{API}/validate/check_mobile_exist` | `mobile` | 手机号是否存在 |
| POST | `{API}/validate/check_email_exist` | `email` | 邮箱是否存在 |
| POST | `{API}/validate/check_sms_correct` | `mobile, captcha, event` | 短信验证码是否正确 |
| POST | `{API}/validate/check_ems_correct` | `email, captcha, event` | 邮箱验证码是否正确 |

依据：`application/api/controller/Sms.php`、`Ems.php`、`Validate.php`、`application/common/library/Sms.php`、`Ems.php`。

## 11. M09 文件上传与附件管理

### 11.1 业务描述

支持后台及会员上传文件，统一记录附件元数据；管理员可搜索、选择、归类和删除附件，会员可查看并选择本人上传的附件。上传库支持本地文件与分片处理，云存储通过插件扩展。

### 11.2 业务规则

1. API 上传要求会员登录；后台上传要求管理员登录。前台 `ajax/upload` 虽位于免登录列表，最终转发到要求会员登录的 API 上传控制器，不能作为匿名上传能力。
2. 普通上传默认上限 `10mb`；默认扩展名包括 `jpg,png,bmp,jpeg,gif,webp,zip,rar,wav,mp4,mp3,webm`。最终配置可能受上传钩子和存储插件影响。
3. 上传库执行大小、可执行文件、文件类型和图片真实性等检查。默认路径模板为 `/uploads/{year}{mon}{day}/{filemd5}{.suffix}`。
4. 附件记录包含当前管理员/会员归属；相同 `url + storage` 的附件在模型插入前做重复检查，该检查不是数据库唯一约束，也不代表按用户独立存一份。
5. 分片上传默认关闭，默认分片大小 2 MiB。启用后按 `chunkid/chunkindex/chunkcount` 保存分片，再合并；`chunkid` 必须满足 36 位小写字母、数字或连字符格式。
6. 分片合并路径将库内最大文件大小临时设为 `1024G`，因此不能把普通上传的 10 MB 上限描述为所有上传模式的统一总大小限制。
7. 附件分类来源于 `site.attachmentcategory`；未分类在页面显示为 `unclassed`，数据库保存空字符串。
8. 后台附件列表支持文件名、类型、时间和分类等筛选，支持图片、音频、视频等类型选择；会员附件查询强制按本人 `user_id` 过滤。
9. 附件归类方法内部额外检查 `general/attachment/edit` 权限；后台附件列表及删除未默认开启个人数据隔离，按入口授权管理。
10. 删除本地附件时触发钩子并尝试删除物理文件，再删除记录；远程文件删除依赖存储插件钩子。当前没有业务引用检查，不承诺删除前会阻止已被引用的附件。

### 11.3 业务流程

**普通上传**：选择文件 → 校验身份 → 校验文件 → 保存文件 → 写入附件元数据 → 返回相对 URL 与完整 URL → 业务表单引用 URL。

**分片上传**：生成分片 ID → 逐片上传 → 提交 `action=merge` 和分片数量、文件名 → 合并并校验 → 保存完整附件 → 清理分片；清理分支通过 HTTP 方法 `CLEAN` 判断，且 `chunkid` 从 POST 参数读取，需客户端适配。

### 11.4 数据模型

| 表 | 字段组 | 说明 |
| --- | --- | --- |
| `attachment` | `id, category, admin_id, user_id` | 主键、附件类别与上传者归属 |
| `attachment` | `url, filename, storage, sha1, extparam` | 路径、原文件名、存储驱动、摘要和扩展参数 |
| `attachment` | `filesize, mimetype, imagewidth, imageheight, imagetype, imageframes` | 文件及图片元信息，大小单位为字节 |
| `attachment` | `createtime, updatetime, uploadtime` | 创建、更新与上传时间 |

### 11.5 API 接口

| 方法 | 路径 | 主要参数 | 权限/返回 |
| --- | --- | --- | --- |
| POST | `{API}/common/upload` | `file*`，可选 `category` | 会员登录；`data.url/fullurl` |
| POST | `{ADMIN}/ajax/upload` | `file*`，可选 `category` | 管理员登录，跳过入口规则鉴权；后台响应 `data.url/fullurl` |
| POST | `{WEB}/ajax/upload` | 同 API 上传参数 | 转发 API 上传，仍需会员登录 |
| POST | 上述上传地址 | 分片：`file, chunkid, chunkindex, chunkcount`；合并：`action=merge, chunkid, chunkcount, filename` | 需要开启分片；分片成功无 URL，合并后返回 URL |
| GET | `{ADMIN}/general/attachment/index` | 通用列表参数 | 对应后台权限；页面/附件列表，附 `fullurl` |
| GET | `{ADMIN}/general/attachment/select` | 列表参数、`mimetype` | 对应后台权限；选择器页面/列表 |
| GET | `{ADMIN}/general/attachment/add` | — | 上传页面；不是附件元数据新增 API，AJAX 直接请求会报错 |
| POST | `{ADMIN}/general/attachment/classify` | `ids*, category` | 需附件编辑权限；批量归类 |
| POST | `{ADMIN}/general/attachment/del` | `ids*` | 对应删除权限；删除结果 |
| GET | `{WEB}/user/attachment` | `offset/limit/search/filter/mimetype` | 会员登录；页面或本人附件 `total/rows` |

依据：`application/common/library/Upload.php`、`application/common/model/Attachment.php`、`application/admin/controller/general/Attachment.php`、各端上传控制器、`application/extra/upload.php`。

## 12. M10 分类与地区字典

### 12.1 业务描述

分类用于给业务内容提供可复用的树形目录；地区字典用于省、市、区县三级联动选择。分类类型、附件类别和配置分组是不同字典，不混用。

### 12.2 业务规则

1. 分类通过 `pid` 支持多级结构；分类类型来自 `site.categorytype`，当前预设 `default/page/article/test`，具体业务由扩展模块使用。
2. 分类支持名称、别名、标志、图片、关键词、描述、自定义名称、状态和权重。
3. 标志可多选 `hot/index/recommend`；新增未指定有效权重时模型设为自身 ID，列表通常按权重、ID 倒序展示。
4. 编辑时不能把自身或后代作为父分类。
5. 分类删除继承通用按 ID 删除逻辑，未实现自动递归删除后代或检查业务引用，不能套用菜单规则的级联删除语义。
6. 分类联动接口只返回 `normal` 状态分类，可按类型、父 ID 筛选。
7. 地区未传省份时读取一级省份；传省份读取二级城市；再传城市读取三级区县。安装 SQL 提供表结构但未提供地区种子记录，实际数据需要导入。

### 12.3 数据模型

| 表 | 字段 | 说明 |
| --- | --- | --- |
| `category` | `id, pid, type, name, nickname, flag, image, keywords, description, diyname, weigh, status, createtime, updatetime` | `pid` 自关联；`flag` 为集合类型；`weigh/id`、`pid` 有索引 |
| `area` | `id, pid, shortname, name, mergename, level, pinyin, code, zip, first, lng, lat` | `level=1/2/3` 对应省/市/区县；`pid` 有索引 |

### 12.4 API 接口

| 方法 | 路径 | 参数 | 权限/返回 |
| --- | --- | --- | --- |
| GET | `{ADMIN}/category/index` | `search, type`，`type=all` 表示全部 | 对应后台权限；页面/分类树列表 |
| GET / POST | `{ADMIN}/category/add`、`{ADMIN}/category/edit` | 编辑传 `ids`；`row[分类字段]`，POST `__token__` | 对应操作权限；页面/保存结果 |
| POST | `{ADMIN}/category/del`、`{ADMIN}/category/multi` | `ids`，批量更新另传 `params` | 通用删除/批量更新 |
| GET | `{ADMIN}/category/selectpage` | SelectPage 参数 | 管理员登录；跳过入口规则鉴权；下拉结果 |
| GET | `{ADMIN}/ajax/category` | `type, pid` | 管理员登录；`data` 为 `[{value,name}]` |
| GET | `{ADMIN}/ajax/area` | `province, city` 或 `row[province/city]` | 管理员登录；`data` 为 `[{value,name}]` |

依据：`application/admin/controller/Category.php`、`Ajax.php`、`application/common/model/Category.php`、`Area.php`。

## 13. M11 系统配置

### 13.1 业务描述

通过动态表单管理站点基础信息、邮件服务、分类字典、会员相关配置及业务自定义变量，并将配置同步为应用可读取的配置文件。

### 13.2 业务规则

1. 配置按 `group` 分组，分组字典来自 `site.configgroup`；当前有基础、邮件、字典、会员、示例分组。
2. 支持字符串、文本、数字、布尔、日期时间、文件/图片、单选/多选、数组及关联选择等动态表单类型；完整类型由配置模型定义。
3. 配置变量名 `name` 唯一；`value` 存值，`content` 存选项字典，`rule/visible/extend/setting` 描述校验、可见性和表单设置。
4. 编辑按变量名批量接收值，数组类数据转 JSON，多选值通常转为逗号串；保存后刷新 `application/extra/site.php`。
5. 新增和删除配置项仅限调试环境 `app_debug=true`；日常配置值编辑不受此开发环境限制。
6. `cdnurl` 不在配置页面展示，源码注释明确不支持在线修改；不能仅据此认定后端字段写入也被严格禁止。
7. 站点名称配置的写入钩子不允许值包含 `fastadmin`，匹配时忽略大小写。
8. 测试邮件使用本次提交配置覆盖当前请求中的邮件配置后发送到指定收件人；测试发送不等于已经保存配置。
9. 数据库配置保存与配置文件刷新不是单个完整事务，文件写入失败时可能出现数据库值和文件值不同步。

### 13.3 业务流程

进入配置分组 → 动态展示对应表单 → 提交变量名和值 → 转换数据类型并写入配置表 → 刷新站点配置文件 → 后续请求按应用配置读取。

### 13.4 数据模型

| 表 | 字段 | 说明 |
| --- | --- | --- |
| `config` | `id, name varchar(30), group, title, tip, type` | 配置身份、分组与展示类型，`name` 唯一 |
| `config` | `value text, content text` | 当前值及选项字典 |
| `config` | `visible, rule, extend, setting` | 可见条件、校验和控件配置 |
| 配置文件 | `application/extra/site.php` | 由配置模型生成的站点配置；上传核心配置另见 `extra/upload.php` |

### 13.5 API 接口

| 方法 | 路径 | 参数 | 权限/返回 |
| --- | --- | --- | --- |
| GET | `{ADMIN}/general/config/index` | — | 配置查看权限；分组配置页面 |
| POST | `{ADMIN}/general/config/add` | `row[name/group/title/tip/type/value/content/rule/visible/extend/setting]`、`__token__` | 调试环境及对应权限；新增表单嵌在配置首页的“+”页签，提交后刷新页面 |
| POST | `{ADMIN}/general/config/edit` | `row[变量名]=值`、`__token__` | 配置编辑权限；保存及刷新文件结果 |
| POST | `{ADMIN}/general/config/del` | `name` | 调试环境及删除权限；按变量名删除 |
| POST | `{ADMIN}/general/config/check` | `row[...]` | 管理员登录；检查配置是否存在 |
| GET | `{ADMIN}/general/config/rulelist` | `keyField, keyValue` | 管理员登录；`list` 校验规则字典 |
| GET | `{ADMIN}/general/config/selectpage` | 配置项 `id` 及 SelectPage 参数 | 管理员登录；按配置项关联表返回下拉数据 |
| POST | `{ADMIN}/general/config/emailtest` | `receiver*, row[邮件配置]` | 对应后台权限；测试发送结果 |
| GET | `{ADMIN}/general/config/get_table_list` | — | 对应后台权限；`data.tableList` |
| GET | `{ADMIN}/general/config/get_fields_list` | `table` | 管理员登录；`data.fieldList` |

依据：`application/admin/controller/general/Config.php`、`application/common/model/Config.php`、`application/extra/site.php`。

## 14. M12 控制台与统计

### 14.1 业务描述

集中展示会员增长、最近活跃、管理员、分类、插件、附件和数据库容量等运行概况，帮助管理员了解当前系统规模。

### 14.2 业务规则

| 指标 | 当前统计口径 |
| --- | --- |
| 会员、管理员、分类总数 | 对应业务表总行数 |
| 今日注册 | `jointime` 位于今日的会员数 |
| 今日登录 | 当前 `logintime` 位于今日的会员数，不是今日登录事件总次数 |
| 近 7/30 日活跃 | 以 `jointime/logintime/prevtime` 三个字段的时间范围查询计算；不是逐日行为日志口径 |
| 近 3/7 日新增 | `jointime` 位于对应时间窗口的会员数 |
| 近 7 日注册趋势 | 从 6 天前到今天按注册日期聚合，缺失日期补 0 |
| 插件总数/启用数 | 本地已发现插件及其启用状态 |
| 附件/图片数量与大小 | 附件表计数及 `filesize` 求和，图片按 `mimetype like image/%` |
| 数据表数量/数据库大小 | `SHOW TABLE STATUS` 的结果及数据、索引大小之和，范围为当前数据库可见表 |

控制台没有新增、编辑或删除业务数据；安装 SQL 中出现的历史权限节点不能证明存在相应业务功能。

### 14.3 数据模型

| 数据来源 | 使用字段/信息 |
| --- | --- |
| `user` | `jointime, logintime, prevtime` 及总数 |
| `admin/category/attachment` | 总数；附件 `mimetype/filesize` |
| 插件文件与数据库元数据 | 插件 `state`、表数据与索引大小 |
| 页面聚合模型 | `totaluser/totaladmin/totalcategory/todayusersignup/todayuserlogin/sevendau/thirtydau/threednu/sevendnu`、附件/插件/容量指标及图表 `column/userdata`；无独立统计落库表 |

### 14.4 API 接口

| 方法 | 路径 | 参数 | 权限/返回 |
| --- | --- | --- | --- |
| GET | `{ADMIN}/dashboard/index` | — | 后台控制台权限；服务端渲染页面，统计数据与图表配置随页面注入 |

当前未提供独立的控制台统计 JSON API。

依据：`application/admin/controller/Dashboard.php`、`application/admin/view/dashboard/index.html`。

## 15. M13 插件管理

### 15.1 业务描述

通过插件机制扩展业务功能，支持插件列表、在线安装、本地上传安装、启用禁用、配置、升级、卸载、测试数据导入和授权检查。

### 15.2 业务规则

1. 插件以 `addons/{name}` 文件目录及元信息识别，当前仓库该目录仅含占位文件，无实际业务插件。
2. 插件名称在管理入口通常要求仅含英文字母和数字。
3. `install/uninstall/local/upgrade/authorization/testdata` 额外限制为超级管理员；启用禁用、配置等按后台规则权限控制。
4. 在线安装、升级、购买/授权检查依赖插件服务和远端市场；本地安装入口也要求市场 `uid/token`，不能描述成完全离线免授权安装。
5. 启用禁用由 `action=enable` 或其他值映射为 `disable`，成功后清菜单缓存。
6. 配置可由插件自定义处理，或写回插件配置文件后刷新服务；支持数组及分组配置。
7. 卸载时仅在传 `droptables`、开启调试且为超级管理员时考虑删除相关表，并过滤为当前前缀和插件名称开头的表。
8. 导入测试数据使用插件的 `testdata.sql`；影响范围取决于插件内容。
9. 已装插件列表可合并市场信息，市场元数据缓存 600 秒；插件服务内部行为属于 Composer 依赖，本文只确认本仓库的调用及限制。

### 15.3 业务流程

选择插件 → 提交身份/版本信息 → 插件服务下载或接收安装包 → 安装并注册资源 → 启用 → 配置 → 业务使用；后续可升级、禁用或卸载。

### 15.4 数据模型

| 实体 | 关键字段/载体 | 说明 |
| --- | --- | --- |
| 插件元信息 | `name, title, intro, author, version, state, url` 等 | 来自插件文件/框架插件服务，无统一 `addon` 业务表 |
| 插件配置 | `name, title, type, value, content, group` 等配置条目 | 保存于插件配置文件或由插件处理 |
| 插件业务数据 | 插件自定义表 | 当前仓库不包含具体插件模型 |
| 框架插件配置 | `application/extra/addons.php` | 自动加载、钩子、路由和优先级等 |

### 15.5 API 接口

以下路径均位于 `{ADMIN}/addon/`，使用后台身份；其中市场 `token` 参数是市场凭证，不是会员登录凭证。

| 方法 | 完整路径后缀 | 主要参数 | 返回/作用 |
| --- | --- | --- | --- |
| GET | `index` | — | 插件管理页及本地插件信息 |
| GET | `downloaded` | `offset/limit/search/filter`，可选 `callback` | 已装插件 `total/rows`，可 JSONP |
| GET / POST | `config` | `name`，POST `row[...]` | 配置页/保存结果 |
| POST | `install` | `name, force, uid, token, version, faversion` | 超级管理员；安装结果，成功附插件信息 |
| POST | `local` | `file, uid, token, faversion, force` | 超级管理员；本地安装结果 |
| POST | `state` | `name, action, force` | 对应权限；启用/禁用结果 |
| POST | `upgrade` | `name, uid, token, version, faversion` | 超级管理员；升级结果 |
| POST | `uninstall` | `name, force, droptables` | 超级管理员；卸载结果 |
| POST | `testdata` | `name` | 超级管理员；测试数据导入结果 |
| POST | `isbuy` | `name, uid, token, version, faversion` | 对应权限；插件服务原始 JSON 结果 |
| POST | `authorization` | `uid, token, faversion` | 超级管理员；授权刷新结果 |
| POST | `get_table_list` | `name` | 管理员登录；`data.tables`，过滤后的关联表名 |

依据：`application/admin/controller/Addon.php`、`application/extra/addons.php`、`composer.json`。

## 16. M14 公共接口与系统辅助能力

### 16.1 业务描述

为客户端提供启动初始化、版本检查、Token 管理和图形验证码，为前后台界面提供语言包、附件后缀图标、缓存刷新及拖拽排序。

### 16.2 业务规则

1. 初始化要求客户端传 `version`，返回版本检查结果和上传地址/CDN 配置。
2. 版本模型查询 `normal` 记录，按 `weigh desc,id desc` 选择与旧版本规则匹配且新版本不同的首条记录；无更新时版本数据为 `null`。安装 SQL 已提供 `version` 表，当前仓库没有独立版本维护控制器。
3. Token 检查和刷新均要求现有 Token 已通过会员登录校验；过期 Token 不能用于刷新。
4. 刷新时先删除当前 Token，再生成有效期 30 天的新 Token，最多尝试 5 次；生成失败会返回错误，旧 Token 已失效。
5. Token 默认 MySQL 存储，也提供 Redis 驱动。MySQL 存储键采用配置的 HMAC 摘要，返回客户端时恢复其提交的原 Token；MySQL 驱动会按日触发一次过期记录清理检查。
6. 公共图形验证码为图片响应；API 公共控制器支持通过 `sid` 请求头建立会话 ID，以便跨端复用验证码会话。`id` 用于区分验证码场景。
7. 语言包按允许语言和存在的控制器加载，返回 `define` JSONP/JavaScript；图标按后缀生成 SVG。
8. 缓存刷新支持 `content/template/addons/browser/all`；浏览器缓存刷新在非调试环境尝试递增 `site.version` 的末段数字。
9. 排序接口按表、主键、ID 顺序更新权重，操作字段限定为 `weigh`，可按 `pid` 进一步过滤。
10. 后台 Ajax 控制器大部分方法跳过入口规则鉴权但仍要求管理员登录。缓存和排序不应被误写为默认仅超级管理员可用。

### 16.3 数据模型

| 实体 | 字段/载体 | 说明 |
| --- | --- | --- |
| `user_token` | `token varchar(50)` 主键、`user_id, createtime, expiretime` | Token 摘要及用户关系；`expiretime=0` 表示不过期，登录默认显式设为 30 天 |
| `version` | `id, status, weigh, oldversion, newversion, downloadurl, packagesize, content, enforce, createtime, updatetime` | 安装 SQL 已提供；`id` 主键，`oldversion/newversion` 为版本字符串，`enforce` 表示是否强制更新 |
| 系统配置/临时状态 | `site.version`、会话验证码、缓存目录、插件缓存 | 无统一的辅助业务表 |
| 可排序业务表 | 主键、`weigh`，可选 `pid` | 由调用方指定目标表 |

### 16.4 API 接口

| 方法 | 路径 | 主要参数 | 权限/返回 |
| --- | --- | --- | --- |
| GET | `{API}/common/init` | `version*` | 公开；`data.versiondata/uploaddata`；是否有更新取决于已配置的版本记录 |
| GET | `{API}/common/captcha` | 可选 `id`，跨端携带 `sid` 头 | 公开；验证码图片 |
| GET | `{API}/token/check` | Token | 会员登录；`data.token/expires_in` |
| POST（调用约定） | `{API}/token/refresh` | 有效 Token | 会员登录；新的 `data.token/expires_in`；源码未强制 POST |
| GET | `{ADMIN}/ajax/lang`、`{WEB}/ajax/lang` | `controllername, lang` | 公开；JavaScript 语言字典 |
| GET | `{ADMIN}/ajax/icon`、`{WEB}/ajax/icon` | 可选 `suffix`，默认 `FILE` | 分别需管理员/会员登录；SVG 图片 |
| POST（调用约定） | `{ADMIN}/ajax/wipecache` | `type` | 管理员登录；缓存刷新结果，源码通过 request 读取参数 |
| POST | `{ADMIN}/ajax/weigh` | `table, ids, changeid`；可选 `field, pk, orderway, pid` | 管理员登录；排序结果 |
| GET | `{API}/index/index` | — | 公开；基础请求成功响应 |
| POST | `{API}/demo/test` | 任意请求参数 | 公开；回显参数，开发示例 |
| GET | `{API}/demo/test1` | — | 公开；`data.action=test1` |
| GET | `{API}/demo/test2` | Token | 仅要求会员登录；`data.action=test2` |
| GET | `{API}/demo/test3` | Token | 会员登录及 `api/demo/test3` 规则权限；`data.action=test3` |
| GET | `{WEB}/index/index` | — | 公开；站点默认首页 |

示例接口用于演示不同认证策略，不代表独立业务模块。版本检查返回字段为 `enforce/version/newversion/downloadurl/packagesize/upgradetext`；升级文案会替换版本号、下载地址和包大小占位符。

依据：`application/api/controller/Common.php`、`Token.php`、`Demo.php`、`Index.php`、`application/common/model/Version.php`、`application/common/library/token/`、前后台 `Ajax.php`。

## 17. M15 系统安装与开发工具

### 17.1 业务描述

向开发与运维人员提供初次安装、按表生成 CRUD、生成权限菜单、导出接口文档、管理插件源码和压缩静态资源的工具，帮助把数据库结构转化为可管理业务模块。

### 17.2 业务规则

1. Web 与命令行安装共用安装实现；安装锁存在时阻止重复安装，命令行可显式使用覆盖参数。
2. 安装检查环境和数据库，导入基础 SQL，写入 `.env`，更新 Token 密钥、管理员密码和站点配置，随机重命名后台入口，写入安装锁并尝试删除 Web 安装脚本。
3. CLI 安装会生成随机初始管理员密码并输出；本文不复制 README 演示站账号密码作为本地初始凭证。
4. CRUD 生成器根据数据库字段、注释和选项生成控制器、模型、验证器、视图、JS 和语言资源；可配置关联、导入及回收站等功能。生成代码不自动等于完成业务规则评审。
5. 通用后台具有列表、增改删、批量更新和 SelectPage 能力。回收站、恢复和彻底删除只有在模型启用软删除并有页面及权限配置时才可作为产品功能。
6. 通用导入辅助方法支持 CSV/XLS/XLSX，但在 trait 中为受保护方法，需要具体业务控制器开放入口；导出主要由前端表格组件提供，当前没有统一导出 API。
7. API 文档生成读取控制器注解，默认输出到 `runtime/docs/`，文件名可配置；禁止以 `api.html` 命名，禁止对 `admin/common` 模块生成。注解可能与实际必填和认证行为不同，接入仍以代码为准。
8. 插件命令用于创建、启停、卸载、刷新、打包或搬移插件等；静态资源构建使用项目 Grunt 任务。

### 17.3 业务流程

安装框架 → 定义业务表及字段注释 → 运行 CRUD 生成器 → 补充业务校验与流程 → 生成菜单和权限 → 分配角色 → 生成 API 文档及构建资源 → 验证后部署。

### 17.4 数据模型

| 数据/产物 | 说明 |
| --- | --- |
| `application/admin/command/Install/fastadmin.sql` | 安装基础表结构与种子数据 |
| `test` 示例表 | 含 `id/user_id/admin_id/category_id/category_ids`、文本、图片、文件、枚举、多选、JSON、金额、日期、权重、状态、软删除字段等，用于演示生成器；未发现相应现成业务控制器，不作为正式业务模块 |
| 生成器输入 | 表名、字段类型、注释、关系和命令选项 |
| 生成器输出 | `application/` 中的控制器/模型/视图/语言资源，`public/assets/js/` 中的页面脚本，`auth_rule` 菜单规则 |
| 安装状态 | `.env`、安装锁、随机后台入口文件及配置文件 |

### 17.5 API 与命令行接口

| 类型 | 入口 | 输入 | 输出/作用 |
| --- | --- | --- | --- |
| GET / POST | `/install.php` | POST：`mysqlHostname/mysqlHostport/mysqlUsername/mysqlPassword/mysqlDatabase/mysqlPrefix`、`adminUsername/adminPassword/adminPasswordConfirmation/adminEmail/siteName` | 初装页面/安装结果；安装成功返回随机后台入口 `data.adminName` |
| CLI | `php think install` | 数据库连接、前缀、可选 `--force` | 初始化系统，输出后台入口与初始管理员信息 |
| CLI | `php think crud -t <不含前缀的表名>` | 控制器、模型、字段、关联、导入等选项 | 生成 CRUD 文件；以命令 `--help` 为完整选项依据 |
| CLI | `php think menu -c <控制器>` | 控制器及规则处理选项 | 创建/维护权限规则 |
| CLI | `php think api -m api` | 模块、控制器、标题、输出文件等 | 生成 HTML API 文档 |
| CLI | `php think addon -a <插件名> -c <动作>` | 插件名、动作及相关参数 | 插件源码和生命周期管理 |
| CLI | `php think min -m all -r all` | 模块、资源类型、优化参数 | 压缩 JS/CSS |
| npm | `npm run build` | Grunt 配置及项目静态资源 | 执行静态资源构建 |

这些是源码现有工具入口，本次仅整理文档，未执行安装、生成、发信或插件变更。

依据：`application/command.php`、`application/admin/command/`、`application/admin/library/traits/Backend.php`、`Gruntfile.js`、`package.json`。

## 18. 依赖、实现差异与待确认事项

本节用于区分产品能力和代码缺口，不代表已经排期的新需求。

| 编号 | 事项 | 现有依据与影响 | 后续确认方向 |
| --- | --- | --- | --- |
| GAP-01 | 联系方式修改认证不一致 | `changeemail/changemobile` 被列为免登录，但方法依赖当前会员对象 | 确认应要求登录；验证无 Token、无效 Token、有效 Token 的行为 |
| GAP-02 | 后台会员新增流程不完整 | 有 `User::add`，无 `admin/view/user/user/add.html`，后台会员模型无新增密码处理钩子；UI 主要提供列表与编辑 | 明确后台是否需要开户，若需要补齐页面、校验与密码处理 |
| GAP-03 | 会员默认分组未指定 | 公共注册未赋 `group_id`，SQL 默认 0 | 明确注册后默认会员组与需鉴权 API 的访问策略 |
| GAP-04 | 唯一性保证层次不一致 | 会员用户名/邮箱/手机依赖代码查询，数据库为普通索引 | 确认并发注册的约束策略与存量数据清理规则 |
| GAP-05 | 密码变更后的会话范围 | 会员改密只删除当前认证实例 Token；找回密码新建的内部上下文 Token 被删除 | 明确是否需要撤销该会员全部历史 Token |
| GAP-06 | 分片上传总大小规则不同 | 普通上传默认 10 MB，合并时库内设为 1024G | 明确业务允许的总大小、分片数量和清理周期 |
| GAP-07 | 分组及分类删除的引用完整性 | 会员组删除未检查会员引用；分类删除未递归或检查引用 | 明确阻止、迁移还是级联删除，避免悬空关系 |
| GAP-08 | 余额积分业务约束待定义 | 无充值/提现流程、业务幂等号和禁止负数约束；后台改分与公共方法的等级联动不同 | 如扩展资产业务，定义账务规则与统一入口 |
| GAP-09 | 插件及地区数据未随仓库提供 | `addons/` 为空；`area` 只有建表无数据 | 按使用场景安装短信/第三方登录/云存储插件并导入地区数据 |
| GAP-10 | 部分接口方法及令牌校验不统一 | 多处仅读取 POST 参数；缓存、刷新 Token 等未显式强制写方法；CSRF 校验按入口实现 | 统一接口契约后再作为对外规范发布 |

## 19. 跨模块验收要点

以下为后续运行验收建议，未表示本次已经执行通过。

| 场景 | 验收要点 |
| --- | --- |
| 管理员认证 | 正常登录、验证码错误、失败次数限制、IP 变化、退出和自动登录符合开关配置 |
| 管理员权限 | 多角色菜单正确；不能管理范围外管理员、分配越权角色或删除本人；角色收权对子级生效 |
| 会员身份 | Web/API 共用账号；三种账号格式登录有效；注册重复检测、禁用账号、短信自动注册行为正确 |
| 联系方式与找回密码 | 事件验证码隔离；错误、过期、超次和已消费验证码被拒绝；登录要求与会话撤销范围得到确认 |
| 附件 | 普通和分片模式分别验证大小及类型；会员只能列出本人附件；删除和云存储钩子行为符合预期 |
| 基础数据与配置 | 树结构无循环；删除引用策略明确；数据库与生成配置一致；邮件测试和保存相互独立 |
| 资产 | 每次有效变化有正确前后值与差额；事务失败无部分提交；等级联动规则一致 |
| 统计 | 注册趋势补零、今日登录与活跃统计使用明确口径，不误作行为事件次数 |
| 插件 | 超级管理员限制生效；启停后菜单刷新；卸载删除表满足既定条件 |

## 20. 资料来源与维护约定

| 来源 | 用途 |
| --- | --- |
| `README.md`、`composer.json`、`package.json` | 产品定位、依赖与工具概况；README 的扩展宣传不直接计入已实现业务 |
| `application/admin/controller/` | 后台模块、操作入口与权限限制 |
| `application/index/controller/`、`application/index/view/` | 前台页面和会员交互 |
| `application/api/controller/`、`application/common/controller/Api.php` | 对外接口、身份验证与响应封装 |
| `application/common/library/`、`application/admin/library/` | 登录、Token、上传、验证码、数据范围等共用规则 |
| `application/common/model/`、`application/admin/model/`、`application/admin/validate/` | 数据关系、字段处理、事件与校验 |
| `application/admin/command/Install/fastadmin.sql` | 已提供的表结构、索引及初始数据 |
| `application/config.php`、`application/extra/`、`application/route.php` | 功能开关、上传参数、站点字典和路由约定 |
| `public/assets/js/backend/`、`application/admin/view/` | 后台实际页面、列表字段与交互入口 |

维护本 PRD 时，应同步更新所属模块的业务规则、数据模型、接口表及待确认项；新增插件或业务模块需单独补充其流程与模型。源码、注解、SQL 和页面不一致时，应记录差异并验证，不能只根据菜单名称推断功能已完成。
