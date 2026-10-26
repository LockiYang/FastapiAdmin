# FastapiAdmin 项目架构与开发指南

本文说明项目的目录、运行链路、开发约定和新增功能流程，供开发者及 AI 按任务查阅。整理日期：2026-10-26；依据当前源码，并吸收根目录 SKILL.md 中仍适用的工程经验。旧技能中的文档站、旧路径及全量验证要求不作为本文的默认流程。

## 1. 总体架构

项目采用同一仓库维护的模块化单体架构：一个 FastAPI 后端，Web 管理端与 uni-app 移动端分别构建，共享业务接口。关系数据库保存业务数据，Redis 承担会话、缓存与部分跨进程协调。

```text
Vue 管理端 / uni-app 移动端
              │ HTTP / WebSocket / SSE
              ▼
开发：Vite 代理或直连     部署：Nginx 静态托管与反向代理
              │
              ▼
FastAPI：中间件 → Controller → Service → CRUD / 存储适配器
              │                    │
              │                    ├─ SQLAlchemy → MySQL / PostgreSQL / SQLite
              │                    ├─ Redis → 会话、缓存、锁、事件分发
              │                    └─ 文件存储与外部登录
              └─ APScheduler → 按节点配置执行定时任务
```

| 子工程 | 主要技术 |
| --- | --- |
| 后端 | Python 3.12+、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic、Redis、APScheduler 3、uv。 |
| Web | Vue 3、TypeScript、Vite、Element Plus、Tailwind CSS 4、Pinia、Axios。 |
| 移动端 | uni-app、Vue 3、Wot UI、UnoCSS、Pinia、Alova。 |
| 部署 | Docker Compose、Nginx，默认编排 backend、MySQL、Redis、Nginx。 |

依赖版本、Node 与 pnpm 要求以各子工程的 `pyproject.toml`、`package.json` 和锁文件为准。前端两个子工程独立安装依赖，不假定存在根目录统一 workspace。

## 2. 目录地图

```text
FastapiAdmin/
├── AGENTS.md                    # AI 开发约定
├── docs/                        # 项目需求、架构与开发日志
├── backend/
│   ├── main.py                  # Typer CLI：run / revision / upgrade
│   ├── pyproject.toml           # Python 依赖、数据库 extras、工具配置
│   ├── pyrightconfig.json       # Python 静态检查配置
│   ├── env/                    # 环境变量模板与本地配置
│   ├── app/
│   │   ├── __init__.py          # 应用工厂与生命周期
│   │   ├── api/v1/routers.py    # 内置路由聚合
│   │   ├── modules/            # system / monitor / task / storage / generator 等
│   │   ├── plugin/             # 自动发现的扩展模块
│   │   ├── core/               # 数据库、权限、调度、中间件等运行机制
│   │   ├── common/             # 枚举、请求与响应等共同约定
│   │   ├── config/             # 配置模型与路径定义
│   │   ├── utils/              # 加密、文件、Excel 等工具
│   │   ├── scripts/            # 数据库与种子初始化
│   │   └── alembic/            # 迁移环境和版本脚本
│   ├── sql/                    # JSON 种子数据
│   ├── templates/              # Python / TypeScript / Vue 生成模板
│   ├── requirements/           # pip / Docker 使用的依赖清单
│   ├── tests/                  # 后端已有测试
│   ├── docs/                   # 后端专项说明与知识资料
│   ├── static/                 # 静态资源、上传文件
│   └── logs/                   # 运行日志
├── frontend/
│   ├── web/                    # Web 管理端
│   └── app/                    # uni-app 移动端
├── docker/                     # Compose、Dockerfile、Nginx、Redis 配置
├── .github/workflows/          # 后端、前端与敏感信息检查
├── deploy.sh                   # 上传代码后的服务器部署入口
└── deploy-artifacts.sh         # 镜像与产物交付脚本
```

`frontend/docs` 文档站已删除，项目说明直接以仓库 Markdown 文档维护。运行时产生的 `.venv`、`node_modules`、`dist`、日志和上传内容不属于业务源码。

### 2.1 业务模块边界

| 模块 | 职责 | 当前开关 |
| --- | --- | --- |
| `system` | 认证、用户、角色、菜单、部门、岗位、字典、参数、公告、工单、版本、日志。 | 内置注册。 |
| `monitor` | 健康检查、在线用户、缓存和服务器监控。 | 当前路由无可选模块判断。 |
| `common` | 通用文件等接口。 | 内置注册。 |
| `task` | 调度任务及任务节点。 | `ENABLED_MODULES` 中的 `task`。 |
| `storage` | 存储源、文件浏览、传输任务与流程。 | `storage`，与定时任务分别启用。 |
| `generator` | 根据数据表生成后端、前端代码。 | `generator`。 |

开关定义在 `backend/app/config/setting.py`，可由环境覆盖；新增可选模块时，要同时考虑路由、生命周期、种子和依赖。当前初始化仍加载全部 ORM 元数据，避免关闭模块后迁移误判为需要删除表；关闭模块不等同于移除表或卸载依赖。

### 2.2 三类路径分开维护

菜单页面地址、API 地址和源码位置各有职责。当前存储与任务后端目录已分离，但 API 仍由 `/task` 域聚合；Web 中也存在沿用 `module_task` 的页面目录。

| 示例 | 当前位置或路径 |
| --- | --- |
| 任务后端代码 | `backend/app/modules/task/` |
| 存储后端代码 | `backend/app/modules/storage/` |
| 任务节点接口 | `/api/v1/task/cronjob/node/...` |
| 文件浏览接口 | `/api/v1/task/storage/browse/...` |
| 菜单一级页面路径 | `/task`、`/storage`，由菜单配置决定。 |
| 文件浏览页面源码 | `frontend/web/src/views/module_task/storage/browse/index.vue` |

改变菜单路径不意味着要同步改变 API。接口地址需核对聚合路由和 Controller 前缀；页面组件位置需核对菜单的 `component_path`。

## 3. 后端运行链路

### 3.1 应用启动与关闭

`main.py run --env=dev|prod` 设置运行环境后启动 Uvicorn，由 `app:create_app` 创建应用。

1. 加载 `setting.py` 与 `env/.env.dev` 或 `.env.prod`；环境变量可覆盖文件配置。
2. 注册异常处理、中间件、内置路由、动态插件、静态资源和 Swagger/ReDoc；存在 `backend/dist` 时注册前端托管。
3. 生命周期中初始化数据库结构、迁移与种子数据。
4. 连接 Redis 并初始化字典、参数缓存。
5. 启用 task 时启动调度协调与任务恢复。
6. 关闭时释放调度器、Redis 和异步数据库引擎。

启动不是只读检查：可能建表、迁移、导入数据和恢复定时任务。不要为验证普通代码修改而自动启动后端。

### 3.2 请求处理

```text
HTTP 请求
  → 中间件：跨域、请求关联 ID、GZip、演示模式与 IP 黑名单等
  → Controller：Schema 参数校验、认证授权依赖
  → Service：业务检查与操作编排
  → CRUD / 适配器：数据库或外部服务访问
  → 统一响应；数据库事务提交，异常时回滚
```

中间件注册见 `setting.py` 的 `MIDDLEWARE_LIST`；生产环境另启 HTTPS 重定向和可信 Host 校验。Controller 通过依赖获取身份、数据库会话和 Redis。统一 JSON 包含 `code`、`msg`、`data`、`status_code`、`success`；全局异常处理转换为 `ErrorResponse`，`OperationLogRoute` 将操作日志安排为后台写入。

`db_getter` 提供请求级 `AsyncSession` 和事务，同一请求通过依赖复用会话。CRUD 主要 `flush`，避免随意自行 `commit` 破坏事务边界。后台任务、WebSocket 等超出 HTTP 请求生命周期的工作，应管理独立会话，不继续使用已结束请求的数据库资源。存储传输现有实现会在事务提交后启动进程内异步任务，可作为事务与后台执行分离的参考。

## 4. 后端开发约定

### 4.1 分层职责

常规业务放在 `app/modules/<业务域>/<功能>/`，遵循相邻模块的结构；简单功能可以按实际需要省略层次。

| 文件 | 责任 |
| --- | --- |
| `controller.py` | 路由、参数、依赖、响应声明；使用现有 `OperationLogRoute`。 |
| `service.py` | 业务规则、数据归属检查、事务内编排、缓存与外部调用。 |
| `crud.py` | 基于 `CRUDBase` 的数据读写和专用查询。 |
| `model.py` | SQLAlchemy 表、字段、索引、约束与关系。 |
| `schema.py` | 输入输出类型、分页与参数校验。 |
| 模块根 `plugin.toml` | 模块名称、版本等描述，不能替代实际路由注册。 |

通用能力放 `core/common/utils/config`，避免将具体业务塞进基础设施。以 `system/dict` 为完整 CRUD 参考，扩展插件可参考 `plugin/module_example/demo`。

| 公共目录 | 职责 |
| --- | --- |
| `common/` | 统一常量、枚举、请求和响应格式。 |
| `config/` | 环境配置、配置模型及项目路径。 |
| `core/` | 数据库、认证授权、中间件、异常、调度与 SSE 等运行机制。 |
| `utils/` | 无状态、可复用的辅助能力。 |
| `plugin/` | 按目录约定自动发现的扩展业务。 |
| `scripts/` | 数据库迁移、种子等启动初始化任务。 |

依赖方向为 Controller → Service → CRUD → Model，业务模块按需依赖 `core/common/utils/config`；避免让基础设施承载具体业务规则。

### 4.2 路由、响应与异常

- 内置模块在 `app/api/v1/routers.py` 聚合；业务 Controller 定义资源前缀，聚合层定义业务域前缀。
- 动态插件放 `app/plugin/module_<名称>/.../controller.py`，顶层定义 `APIRouter`，由 `core/discover.py` 在应用创建时扫描。插件导入失败、路由冲突会中止启动；新增插件后需要应用重新创建，不能假定现有进程会热插入路由。
- 普通 JSON 返回 `SuccessResponse`，声明 `ResponseSchema[T]` 等现有输出模型；业务失败抛 `CustomException`，沿用共同的返回码。文件、流式响应沿用各自协议。
- 权限标识前后端一致，例如 `module_system:dict_type:create`，不要照搬旧技能里的不匹配示例。

### 4.3 认证、权限和数据范围

- HTTP 使用现有认证依赖；当前认证包含 JWT、Redis 会话及数据库用户状态检查。
- Controller 用 `Security(AuthPermission([...]))` 校验功能权限。`is_superuser=true` 是超管身份，不由角色名 `SUPER_ADMIN` 决定。
- 数据范围由 `Permission` 等现有机制处理，当前范围含本人、部门及子部门、全部；角色范围查询排除停用和已删除角色。
- 不假定所有自定义 SQL、详情、批量写入都会自动应用数据范围。新增接口需逐一确认查询和写入的授权边界。
- `ModelMixin` 提供通用字段；`UserMixin` 的创建、更新、删除人员外键指向 `sys_user`。新增其他用户体系或商户归属时，应设计明确字段，不复用后台员工 ID 表示另一类身份。
- 当前部门数据范围不能直接当成完整多租户隔离；已有移动端也不能据此认定存在独立前台会员模型。

### 4.4 数据库与种子

- ORM 元数据和迁移环境共同决定结构；模型变化要考虑字段兼容、约束和迁移方案。
- 业务数据库读写使用异步引擎和会话；同步引擎供调度任务存储、代码生成等同步组件使用。配置由 `ASYNC_DB_URI`、`DB_URI` 等分别提供，不将同步驱动地址传给异步组件。
- 空库按模型创建表；已有库应用迁移；dev 环境还会尝试自动生成和应用模型变更。结构变更操作需要在适当环境执行，普通文档任务不运行迁移。
- `sql/<表名>.json` 是预置数据，不是数据库自动导出物；表已有任意数据时整表跳过初始化。后台配置不会自动回写 JSON。
- 菜单、部门的 `children` 递归建立父子关系；字典项由 `dict_type` 解析 `dict_type_id`；其他种子通常直接传给模型，关联 ID 必须保持一致。
- 调整菜单等预置规则时，区分新库种子与已有库更新；不要通过清库使改动生效。
- 新增查询、分页或状态字段时，以当前 Schema、模型和业务模块为准，不从旧注释推断统一枚举。

## 5. Web 前端开发约定

### 5.1 目录和请求

| `frontend/web/src/` 下的位置 | 用途 |
| --- | --- |
| `api/module_x/` | 资源 API 与请求、响应类型。 |
| `views/module_x/` | 业务页面；页面私有组件放同级 `components/`。 |
| `components/` | 公共 `FaXxx` 组件。 |
| `hooks/core/` | 表格、表单、弹窗、权限、导入导出等组合式能力。 |
| `router/` | 静态路由、守卫、菜单转换与动态注册。 |
| `store/modules/` | 用户、菜单、工作标签、配置等 Pinia 状态。 |
| `utils/http/` | Axios 封装、令牌处理、错误处理与会话续期。 |
| `directives/permission/` | `v-hasPerm` 等界面权限。 |
| `locales/langs/`、`styles/` | 中英文词条与主题、布局样式。 |

API 使用现有 `request`，通常从 `@utils` 导入；类型使用 `ApiResponse<T>`、`PageResult<T>` 等现有约定。当前响应拦截器返回 Axios response，调用方按既有方式读取 `response.data`，不要假定直接得到业务 `data`。业务失败和多数提示已有全局处理，页面应避免重复提示。

### 5.2 页面与交互

- CRUD 页面优先组合 `useTable`、`useTableColumns`、`useCrudDialog`、`useCrudForm`、`useImportExport`，复用 `FaTable`、`FaSearchBar`、`FaDialog` 等组件。
- Vue 等常用 API 由 Vite 自动导入；新增引用前核对当前插件配置。`src/types` 下部分声明为构建生成物，缺失时应区分环境问题与代码错误。
- 通用文案按现有国际化方式维护 `zh.json`、`en.json`，使用项目主题变量和样式，避免新增重复基础组件。
- 按钮权限与后端标识对齐；前端隐藏按钮只控制展示，服务端仍须授权。
- 需要更新界面的异步任务状态应使用同一响应式对象，避免将普通对象放入响应式列表后继续在回调中修改原始对象。

### 5.3 菜单、路由和缓存

业务路由从后端菜单生成：`guards.ts` → `MenuProcessor.ts` → `route-loader.ts` 的 `RouteRegistry`。`routes.ts` 提供静态壳层，当前 Router 使用 Hash 模式。

新增菜单要核对 `route_path`、`route_name`、`component_path`、`redirect` 和 `keep_alive`。`component_path` 必须对应真实 Vue 页面；页面通过 `defineOptions({ name })` 声明与菜单 `route_name` 一致的组件名。

页面级 KeepAlive 入口是 `layouts/fa-page-content/index.vue`，目录路由不挂中间壳组件，缓存键为叶子路径 `path`，query 变化不会创建新实例。工作标签及 `include/exclude` 管理缓存集合；不要随意增加第二层 KeepAlive 或 `max`，也不要删除退出登录时的缓存驱逐逻辑。

带 WebSocket、定时器或全局事件监听的缓存页面，需要处理 `onActivated`、`onDeactivated` 和卸载清理。WebSocket 防重入覆盖 CONNECTING 状态，沿用 `ws && ws.readyState !== WebSocket.CLOSED` 等现有守卫；主动关闭前清理回调，避免重复连接与提示。WebSocket 鉴权工具支持通过 `Sec-WebSocket-Protocol` 传令牌，新增实时接口时需同时维护客户端与后端握手协议。

## 6. 移动端开发约定

移动端在 `frontend/app` 独立安装、构建，入口为 `src/main.ts`、`src/App.vue`；页面位于 `src/pages` 和 `src/subPages`，页面配置见 `src/pages.json`，路由封装见 `src/router`。

- UI 使用 Wot UI、UnoCSS 和现有主题能力，不能直接照搬 Web 的 Element Plus 页面。
- API 独立放在 `src/api`；`src/http` 通过 Alova 的 uni-app 适配器处理请求；状态位于 `src/store`。
- 变更公共后端接口时，评估 Web 与移动端调用方是否都要修改；页面导航与权限分别检查。
- 微信登录、上传、WebSocket 等涉及平台差异，检查实际目标平台，不能用 H5 行为代替小程序实测结论。
- 此处只说明目录与通用约定，不自动启用 `frontend/app/.agents/skills` 中的技能。

## 7. 调度、存储与实时任务

| 能力 | 当前实现与开发注意事项 |
| --- | --- |
| 定时调度 | APScheduler，仅使用 MemoryJobStore 与一个线程池；任务表为唯一配置来源，启动先加载定义再调度，事务提交后同步内存计划。仅支持一个后端实例、`WORKERS=1`。监控只读计划与日志、支持全局暂停/恢复；任务管理统一修改配置。 |
| 内置任务 | `builtin:<模块名>[.<函数名>]` 从 `modules/task/node/handlers` 解析处理器；原始代码块受 `SCHEDULER_ALLOW_CODE_EXEC` 控制，默认关闭。 |
| 文件存储 | `modules/storage/core` 适配本地、FTP/FTPS、SFTP 及 S3、OSS、COS、OBS 等存储；浏览、传输、流程模块调用适配层。 |
| 传输任务 | 记录任务与步骤，在进程内异步执行，通过 SSE 推送状态。不能据此假定已有独立分布式任务队列或进程退出后自动续跑。 |

Redis 除登录会话、字典和参数缓存外，还用于验证码与 SSE 跨进程 Pub/Sub；不再保存调度计划。SSE 连接及事件分发见 `core/sse_manager.py`。Redis 初始化连接失败会中止启动，不能把它当作可有可无的缓存。

开发异步功能要明确事务提交时机、进度状态、取消与失败处理、断连资源释放；是否支持恢复应以实际实现为准。存储和定时任务是独立模块，不因页面历史位置而互相强制依赖。

## 8. 新功能开发流程

1. **确定需求**：查阅 `prd.md` 对应部分，明确用户、接口权限、数据归属、状态和异常行为；确认涉及 Web、移动端还是两端。
2. **确定边界**：选择现有业务域、新可选模块或动态插件，参考相邻实现，列出受影响的接口、表、菜单和客户端。
3. **后端实现**：定义 Model 和 Schema，补充 CRUD、Service、Controller，落实查询与写入权限；注册路由，可选模块补齐开关处理。
4. **数据方案**：确定迁移、新库种子和已有库更新方式。需要代码生成时审查 `templates/{python,ts,vue}` 及生成结果；生成物并不免于授权和业务检查。Jinja2 循环内赋值有作用域，跨循环统计优先用过滤器或 namespace。
5. **前端实现**：新增 API 类型与方法，复用表格、表单组件，配置菜单和按钮权限，核对组件名、动态路由与缓存。跨端接口同步调整移动端。
6. **最小验证**：检查差异、调用引用、字段和权限契约；按改动与用户要求选择局部检查。普通开发不自动运行全量测试、启动服务、迁移或部署。
7. **文档交付**：业务规则变化更新 `prd.md`，架构变化更新本文，并在 `dev.md` 写明实际改动、验证与遗留事项；发布时再整理 CHANGELOG。

## 9. 本地命令与检查边界

以下供按需使用，不是每次任务的执行清单。

| 工作目录 | 命令 | 说明 |
| --- | --- | --- |
| `backend/` | `uv sync --extra mysql` | MySQL 驱动；PostgreSQL 对应 `--extra postgres`，SQLite 对应 `--extra sqlite`。 |
| `backend/` | `uv run main.py run --env=dev` | 启动服务，可能触发数据库和任务状态变更。 |
| `backend/` | `uv run main.py revision --env=dev -m "说明"` | 在合适数据库环境生成迁移供审查。 |
| `backend/` | `uv run main.py upgrade --env=dev` | 应用迁移。 |
| `frontend/web/` | `pnpm install`、`pnpm dev` | 安装与开发服务。 |
| `frontend/web/` | `pnpm ts:check` | Vue/TypeScript 类型检查。 |
| `frontend/web/` | `pnpm build:prod` | Vite 生产构建；该命令本身不包含完整类型检查。 |
| `frontend/app/` | `pnpm dev:h5`、`pnpm dev:mp-weixin` | 启动 H5 或微信小程序开发。 |
| `frontend/app/` | `pnpm type-check` | 移动端类型检查。 |

复制环境模板后按使用的数据库配置连接，MySQL/PostgreSQL 需准备可连接的数据库服务与数据库，Redis 也需可用；SQLite 省去独立数据库服务，不能免除其他运行依赖。端口、API 前缀和 WebSocket 端点以当前环境配置为准，后端默认端口为 8001。

Web HTTP 默认通过 `VITE_APP_BASE_API` 前缀请求，开发代理目标为 `VITE_API_BASE_URL`；监控与存储传输 SSE 使用 `VITE_APP_WS_ENDPOINT` 指定的实时服务基址，并将 `ws/wss` 转为 `http/https`。API 代理配置不会自动替代该基址。

验证与 AI 行为遵循 AGENTS.md：未经用户要求不新增或修改测试脚本，不默认运行 pytest、Vitest 或全量检查。Web 的 `pnpm lint` 包含批量自动修复，不作为普通任务的无副作用检查。仓库 CI 独立配置后端 Ruff/pytest、Web 构建/类型检查/测试及移动端类型检查，不代表本地每次都需要全量执行。

## 10. 构建与部署边界

| 产物位置 | 使用场景 |
| --- | --- |
| `frontend/web/dist` | Web 构建输出。 |
| `docker/nginx/web/dist` | Nginx `/web` 使用的静态文件。 |
| `backend/dist` | 后端直接托管 Web 的可选目录。 |
| `docker/nginx/app/dist/build/h5` | Nginx `/app` 使用的移动端 H5 产物。 |

构建时的前端 base 与目标入口要匹配。当前 Nginx 根路径 `/` 跳转 `/web/`，API 通过 `/api/v1` 代理，原文档站挂载已移除；Swagger/ReDoc 是独立的后端接口文档。

只有交付或部署任务才按目标重建、同步所需产物；不要每次修改前端都同步全部目录。源码修改不会自动更新已部署产物。同步哈希静态文件时应清理目标内旧资源，先核对源与目标，避免覆盖上传数据。`register_frontend` 的目录检查和托管都使用 `path_conf.FRONTEND_DIST_DIR`。

`deploy.sh` 与 `deploy-artifacts.sh` 会构建、传输或重启服务，不属于静态验证工具；依照用户授权和实际部署方案执行。

上传文件目录需独立持久化。Compose 当前将宿主机 `docker/backend/static/upload` 挂载到后端容器的 `/home/static/upload`，重建镜像不能代替保留该目录。Nginx 除 HTTP API 外也转发 WebSocket；后端可按部署需要直接用 Uvicorn 运行。

### 10.1 日志与健康检查

- `core/logger.py` 使用 Loguru 输出控制台和轮转文件日志，日志目录由 `config/path_conf.py` 定义，位于 `backend/logs/`。
- `CorrelationIdMiddleware` 通过 `X-Correlation-ID` 关联请求上下文，排查时结合响应、运行日志与操作日志，不只看前端提示。
- `/api/v1/monitor/health/check` 检查数据库和 Redis 连通性；通过健康检查不代表所有业务、外部存储或定时任务都已验证。
- Swagger/ReDoc 用于查看接口契约；外部访问范围还受 Nginx 配置约束。

## 11. 维护本文的原则

目录、模块开关、路由机制、事务边界、公共组件或部署入口变化后，同步维护相关章节。将当前行为、建议约定和未来设计分开；文档与代码不一致时说明差异并按任务修正。记录具体问题时链接源码或开发日志，避免把未经核实的历史结论复制成当前架构。
