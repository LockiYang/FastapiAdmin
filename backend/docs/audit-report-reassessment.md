# 历史审计报告现状复核

复核日期：2026-10-08  
复核对象：[DSH 全栈审计总报告](../../dsh/AUDIT-REPORT.md)  
范围：当前工作区的源码、种子数据、配置样例、Docker 编排和 CI 配置。**未运行测试、服务、数据库查询或线上探针**。以下“仍存在”表示能从当前源码确认该条件，不能替代运行时漏洞复现；历史报告中的线上状态、凭据吊销及镜像内容也无法由本次静态审查证明。

## 结论

总报告的 §2–§3 记录的是 2026-10-04 发现问题时的状态；§9.1 又记载同轮修复。不能把 §2 的每条结论直接作为现在的待办。当前最需要处理的是**数据范围对批量写入不生效、公告发布状态契约冲突、会话权限缓存未及时失效**。另外，非 Docker 部署仍可落到公开的开发密钥默认值；新库的公开种子口令仍需在正式环境更换。

## 当前仍有证据支持的问题

| 优先级 | 问题与当前证据 | 影响与建议 |
| --- | --- | --- |
| 高 | **批量写入绕过数据范围。** [CRUDBase 查询](../../backend/app/core/base_crud.py)的 `_build_conditions()` 会追加 `Permission._permission_condition()`；但同文件的 `delete()`、`clear()`、`set()` 直接按 ID 或全表执行 SQL。`NoticeService.set_available()` 直接调用 `set()`；`DeptService.set_available()` 虽读取可见部门，却没有校验传入 ID 全部属于可见集合。[数据权限实现](../../backend/app/core/permission.py)也明确只在被调用时生成条件。 | 拥有对应按钮权限的非超管可能修改数据范围外的记录。先审计每个 Service 的写入入口，再对目标 ID 做可见性校验，或让通用批量写入附加权限条件；同时确认操作影响行数。此项是源码级风险判断，未做越权请求复现。 |
| 高 | **公告状态契约冲突。** [后端模型](../../backend/app/modules/system/notice/model.py)和 [Schema](../../backend/app/modules/system/notice/schema.py)规定 `0=草稿、1=已发布、2=已归档`；但 [Web 公告页](../../frontend/web/src/views/module_system/notice/index.vue)把 `0/1` 显示为“启用/停用”，筛选和编辑都没有归档选项。更值得注意的是 [NoticeService.available_page()](../../backend/app/modules/system/notice/service.py)使用 `status=0` 获取“已启用公告”，而该值按模型是“草稿”。 | Web 会误显示、误修改状态；若 `available_page()` 用于面向用户的公告展示，草稿有被展示的风险。应先确定唯一状态含义，再同步模型、查询、Web 筛选/编辑、移动端和种子数据。 |
| 高 | **会话与授权未随变更完全失效。** [认证依赖](../../backend/app/core/dependencies.py)每请求查库确认用户仍存在且未删除，这是相对历史报告的部分改进；但停用判断取 Redis 会话里的 `user_status`，按钮权限取会话里的 `permissions`，没有在此核对数据库中的最新状态/角色。[用户服务](../../backend/app/modules/system/user/service.py)改密、停用和调整角色时没有统一撤销该用户全部会话的步骤。 | 已登录用户的停用、撤权或改密可能延迟生效，直到会话过期/登出；删除用户则会被查库拦住。建议在敏感变更后按用户索引撤销会话，或使用会话版本号并在每次请求校验。 |
| 高 | **非 Docker 启动仍有固定 JWT 密钥默认值。** [Settings.SECRET_KEY](../../backend/app/config/setting.py)仍有源码默认字符串，且没有生产环境专门校验；[Docker Compose](../../docker/docker-compose.yaml)使用必填插值强制提供密钥。 | 旧报告“生产必用默认密钥”的断言已不适用于当前 Compose，但直接运行后端且漏配密钥仍可能使用公开值。建议生产配置启动时拒绝默认值；实际线上密钥是否已轮换不能从仓库确认。 |
| 中 | **新库仍导入公开的示例账号。** [用户种子](../../backend/sql/sys_user.json)包含 `super`、`admin`；[README](../../README.md)公开演示口令。初始化逻辑在 `sys_user` 空表时导入种子。历史报告称已复算种子哈希对应公开口令，本次未重复验证哈希。 | 历史报告称线上口令已轮换，本次不能验证；新环境若直接对外开放仍需核对账号和口令。正式环境应在开放访问前更换/禁用种子账号，并核对超管身份。 |
| 中 | **部门/菜单关系成环时递归没有保护。** [get_child_recursion()](../../backend/app/utils/common_util.py)只追加 ID 后递归，没有 visited 集合；[菜单服务](../../backend/app/modules/system/menu/service.py)、[部门服务](../../backend/app/modules/system/dept/service.py)及[数据范围查询](../../backend/app/core/permission.py)会调用它。 | 一旦形成环，相关请求可能递归失败。应阻止把节点挂到自身/后代，并让递归函数在坏数据下也能终止。当前未证明普通页面一定可以制造环。 |
| 中 | **Web 富文本默认上传地址仍不匹配后端接口。** [编辑器](../../frontend/web/src/components/forms/fa-wang-editor/index.vue)默认拼 `${VITE_API_URL}/file/upload`；[后端文件路由](../../backend/app/api/v1/routers.py)挂在 `/common` 下，接口实际为 `/api/v1/common/file/upload`。仓库仅在开发 `.env.development` 设置 `VITE_API_URL=/`，生产样例未设置该变量。 | 使用默认上传配置时，公告/工单图片上传可能请求错误地址；自定义 `uploadConfig.server` 可绕过。应使用统一请求根路径和正确的 `/common/file/upload` 接口，并确认上传响应格式。 |
| 中 | **移动端通用 JSON 请求头拼写错误。** [alova 适配器](../../frontend/app/src/http/adapters/alova.ts)写 `ContentType`，不是 `Content-Type`；个别 API 单独设置正确头，不能覆盖所有通用请求。 | 服务端/代理可能按意外的媒体类型解析请求。修正后需分别核对 JSON、表单和文件上传路径。 |
| 中 | **公开注册接口没有独立开关。** [用户注册 Controller](../../backend/app/modules/system/user/controller.py)无需登录即可调用，[Service](../../backend/app/modules/system/user/service.py)直接建普通用户。演示模式中间件可阻止部分写请求，但其配置或 Redis 加载失败时会默认关闭。 | 如果产品不需要自助注册，应增加明确开关；如果需要，应明确验证码、频控、默认权限与审计规则。不能把演示模式当作注册功能开关。 |
| 低 | **ValueError 回显异常文字。** [全局异常处理器](../../backend/app/core/exceptions.py)记录日志后仍将 `str(exc)` 返回给客户端。 | 内部抛出的 `ValueError` 可能携带不应公开的细节。可给用户返回固定文案，把具体内容只记日志；预期的输入错误改用明确的业务异常。 |

**产品差距，需单独决策：** [REQUIREMENTS.md](../../REQUIREMENTS.md)描述 `tenant_id` 行级隔离，而当前 [Permission](../../backend/app/core/permission.py)实现的是用户/部门数据范围，未发现通用租户过滤层。这是“目标规格与现有产品不一致”，不能仅凭旧审计报告把它当成已获批准的开发任务。Web 菜单国际化与移动端功能范围也需要独立产品验收标准。

## 历史问题在当前源码中的状态

| 历史报告条目 | 本次静态核对结果 |
| --- | --- |
| Dockerfile 无法构建（§2.4） | [Dockerfile](../../docker/backend/Dockerfile)现已复制 `backend/requirements/` 并从分层 requirements 安装；旧原因不再成立。**未实际构建镜像。** |
| 生产 CORS 通配、代理信任 `*`（§2.5） | [Settings.ALLOW_ORIGINS](../../backend/app/config/setting.py)在生产未配置域名时返回空列表；[Compose](../../docker/docker-compose.yaml)的 `FORWARDED_ALLOW_IPS` 默认是网段，不是 `*`。仍需核对部署环境是否覆盖这些值。 |
| 代码生成即 RCE、定时任务默认 `exec`（§2.3） | [生成器](../../backend/app/modules/generator/gencode/jinja2_template_util.py)现有上下文清洗和结构检查；[模板安全实现](../../backend/app/modules/generator/gencode/template_safety.py)对代码位置做白名单处理。[调度器开关](../../backend/app/config/setting.py)默认 `False`。模板的 `autoescape=False` **仍存在，但不能单独证明漏洞仍在**；本次没有执行对抗载荷，不能重新确认其绝对安全。 |
| 登录业务异常 500（§2.5） | [CustomException 处理器](../../backend/app/core/exceptions.py)现按业务码映射 HTTP 状态；历史报告 §9.1 记载已修。**未发起实际登录请求。** |
| 移动端刷新令牌、头像上传、生产 WS 地址（§3.2–4） | [刷新接口](../../frontend/app/src/api/module_system/auth.ts)改为 JSON 字符串；[头像接口](../../frontend/app/src/api/module_system/user.ts)改为 `/common/file/upload`；[生产 WS 配置](../../frontend/app/.env.production)使用 `wss://` 服务域名。静态证据显示旧写法已不存在。 |
| Web 生产构建开关（§3.6） | [Vite 配置](../../frontend/web/vite.config.ts)已识别 `production` 模式；旧 `mode === "prod"` 恒假的结论过期。 |
| “无 CI、迁移链路 0 覆盖”（§1、§5） | [后端 CI](../../.github/workflows/backend-ci.yml)、[前端 CI](../../.github/workflows/frontend-ci.yml)和[迁移守卫](../../backend/tests/test_migrations.py)均已存在。迁移守卫明确只覆盖 SQLite 自举与模型一致性，不代表 MySQL/PostgreSQL 升级链路已覆盖。 |

## 不能由本次审计确认的事项

- 历史报告 §4、§9、§10 中的公网端口、API 文档访问控制、容器用户、TLS、健康检查、证书续期、镜像卫生和线上行为，都是**当时**的环境证据；当前仓库配置不能证明正在运行的环境与之相同。
- 历史仓库中的 OpenAI Key、数据库口令和加密旧密钥是否已吊销/轮换，需由凭据持有人核对；本次未读取或输出任何真实密钥。
- 历史报告 §9.2 标题为“仍未处理”，其中又列“凭据轮换与镜像卫生（已处理）”“仓库密钥防回归（已落地）”等已完成项。该节不能整体作为待办列表；需逐条对照当前事实。
- 本次未核算 Web i18n 覆盖率、未穷举所有 best-effort 异常分支，也未核对第三方 SDK、实际数据或浏览器行为；历史的数量和通过率不能作为本次统计。

## 建议处理顺序

1. 先处理批量写入的数据范围与会话撤权，结合非超管账号做权限边界验证。
2. 统一公告状态契约，核对 `available_page()` 是否会向用户展示草稿，再改 Web 与移动端。
3. 处理生产密钥启动校验及新库种子账号交付流程；核对公开注册是否属于产品需求。
4. 修复富文本上传地址、移动端请求头和树形关系防环。
5. 最后由环境负责人复核报告中的线上/密钥历史结论，更新原报告的过期状态与失效行号。
