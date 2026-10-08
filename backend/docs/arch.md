# Backend 技术架构

## 1. 架构概览

后端是 **Python 3.12+ / FastAPI 单体服务**，按业务域划分模块，通过 Uvicorn 提供 HTTP、WebSocket 和 SSE 接口。主要组件是 Pydantic v2、SQLAlchemy 2、Alembic、Redis 和 APScheduler。外部调用经路由进入业务层，再访问数据库、缓存或第三方服务。

```text
Web / App / API 客户端
         │  HTTP / WebSocket / SSE
         ▼
Nginx（Docker 部署时：TLS、静态资源、/api/v1 代理）
         ▼
FastAPI + Uvicorn（中间件、路由、依赖注入）
         ▼
Controller → Service → CRUD / 适配器
                         ├─ MySQL / PostgreSQL / SQLite
                         ├─ Redis
                         └─ 对象存储、FTP/SFTP、AI 模型服务等
```

## 2. 代码分层与模块

| 位置 | 职责 |
| --- | --- |
| `main.py`、`app/__init__.py` | CLI 入口、FastAPI 应用工厂与启动/关闭生命周期。 |
| `app/api/v1/routers.py` | 聚合内置路由；外部 API 位于 `/api/v1` 下。 |
| `app/modules/<业务域>/` | 按域组织功能。`controller.py` 处理协议与参数，`service.py` 实现业务规则，`crud.py` 访问数据，`schema.py` 定义 Pydantic 模型，`model.py` 定义 ORM 模型；部分功能按需省略文件。 |
| `app/core/` | 数据库和 Redis 连接、认证授权、基础 CRUD、中间件、异常、日志、调度器与 SSE 管理。 |
| `app/common/`、`app/utils/` | 响应格式、枚举、常量及通用工具。 |
| `app/config/`、`env/` | Pydantic Settings 配置；按 `ENVIRONMENT` 读取 `.env.dev` 或 `.env.prod`，环境变量可覆盖配置。 |
| `app/plugin/`、`templates/` | 二次开发插件与代码生成模板。启动时扫描 `module_*/**/controller.py` 并注册插件路由。 |

内置业务域包括：`system`（用户、角色、菜单、部门、字典、参数、认证等）、`monitor`（健康、缓存、在线用户、服务器）、`task`（定时任务）、`storage`（存储传输）、`ai`（AI 对话）、`generator`（代码生成）、`common`（文件）。`task` 和 `storage` 的接口路径为兼容现有前端，仍保留 `/task/cronjob` 与 `/task/storage`。路由冲突或插件导入失败会在启动时终止应用，避免接口静默缺失。

## 3. 请求与安全链路

1. 中间件处理 CORS、请求 ID、GZip、演示模式与 IP 黑名单；生产环境另启 HTTPS 重定向、可信 Host 校验。
2. Controller 用 Pydantic 校验输入，通过依赖注入获取身份、Redis 和请求级 `AsyncSession`；一次普通 HTTP 请求的数据库操作共享事务，成功提交，异常回滚。
3. 登录签发 JWT，认证依赖同时校验 JWT、Redis 会话及数据库中的用户状态；`AuthPermission` 检查接口权限，`Permission` 在查询中施加本人、部门及子部门、全部数据范围。
4. Service 调用 CRUD 或外部适配器。普通接口使用统一响应结构（`code`、`msg`、`data`、`status_code`、`success`）；异常由全局处理器转换为响应。操作日志由自定义路由异步写入数据库。

## 4. 数据、任务与实时通信

| 组件 | 使用方式 |
| --- | --- |
| 关系数据库 | SQLAlchemy 异步会话承载业务数据；支持 MySQL、PostgreSQL、SQLite。同步引擎仅供调度任务存储和代码生成等同步组件使用。Alembic 管理结构变更；启动时应用已有迁移、初始化空库和种子数据，开发环境还检查模型变更并生成迁移。 |
| Redis | 存储登录会话、系统参数/字典缓存、验证码等临时状态；提供调度选主锁、默认任务存储和 SSE 跨进程 Pub/Sub。连接失败会中止启动。 |
| APScheduler | 管理定时任务；默认使用 RedisJobStore，同时配置 SQLAlchemy 与内存任务存储。多 Worker 通过 Redis 锁选出一个调度进程。 |
| 存储传输 | 适配本地、FTP/FTPS、SFTP、S3、OSS、COS、OBS；任务及步骤落库后，由进程内异步任务执行，进度写库并通过 SSE 推送。传输流程提供节点与连线编排。 |
| AI 聊天 | Agno 组织 Agent/Team，调用兼容 OpenAI 接口的模型服务；会话使用 Agno 的数据库表，聊天消息经 WebSocket 传输。 |

## 5. 启动、部署与运维

- **启动顺序**：`main.py run --env=dev|prod` → `create_app()` 注册异常处理、中间件、路由和静态资源 → 生命周期初始化数据库/种子数据、Agno 表、Redis/缓存、调度器；关闭时释放这些资源。
- **部署形态**：仓库的 Docker Compose 使用 Nginx、backend、MySQL、Redis 四个服务；Nginx 代理 `/api/v1`，并转发 WebSocket。上传文件目录挂载到宿主机持久化。也可直接运行 Uvicorn，数据库由配置选择。
- **可观测性**：Loguru 输出控制台与轮转文件日志；`X-Correlation-ID` 关联请求日志；`/api/v1/monitor/health/check` 检查数据库和 Redis 连通性；Swagger UI / ReDoc 提供接口文档。
- **开发入口**：`main.py revision` / `upgrade` 管理迁移；`tests/` 使用 pytest，依赖和质量工具定义在 `pyproject.toml`。安装与命令细节见 [Backend README](../README.md)。

## 6. 这些目录如何共同工作

### 6.1 启动阶段

应用创建入口是 `app/__init__.py` 中的 `create_app()`：

```text
读取 config
  ↓
create_app()
  ├─ 注册异常处理 core.exceptions
  ├─ 注册中间件 core.middlewares
  ├─ 注册内置路由 app.modules
  ├─ 动态注册 app.plugin
  ├─ 注册静态文件
  ├─ 注册 Swagger / ReDoc
  └─ 注册前端资源
  ↓
lifespan 启动
  ├─ scripts.initialize 初始化数据库、迁移和种子数据
  ├─ 初始化 AI 会话表
  ├─ core.redis_crud 连接 Redis
  ├─ 初始化系统参数和数据字典缓存
  └─ core.ap_scheduler 启动定时任务调度器
```

应用关闭时，生命周期依次停止调度器、关闭 Redis，并释放数据库连接池。

### 6.2 请求阶段

以插件中的“新增示例”接口为例：

```text
POST /example/demo/create
  ↓
middlewares.py
  ├─ 生成请求关联 ID
  ├─ 检查 IP 黑名单
  ├─ 检查演示环境写操作限制
  └─ 处理 CORS、HTTPS 和 GZip
  ↓
controller.py
  ├─ Schema 校验请求参数
  ├─ AuthPermission 校验登录与接口权限
  └─ db_getter 创建数据库会话和事务
  ↓
service.py
  └─ 执行业务规则，例如检查名称是否重复
  ↓
crud.py / CRUDBase
  └─ 通过 SQLAlchemy 执行 INSERT，并 flush 到数据库
  ↓
db_getter 正常结束并提交事务；发生异常则回滚
  ↓
SuccessResponse 返回统一 JSON
  ↓
OperationLogRoute 在后台写入操作日志
```

全局异常由 `core.exceptions` 捕获并转换成统一的 `ErrorResponse`。需要缓存、会话或跨进程协调时，Service 和依赖通过 `core.redis_crud` 访问 Redis。

### 6.3 分层协作原则

```text
Controller：处理 HTTP 协议、参数、依赖注入和响应
Service：实现业务规则并编排操作
CRUD：封装数据库读写
Model：定义数据库表结构和关系
Schema：定义接口输入、输出和字段校验
```

六个公共目录的定位如下：

```text
common   统一常量、枚举、请求和响应约定
config   管理环境配置和项目路径
core     提供数据库、认证、权限、异常、中间件等运行机制
plugin   承载按约定自动发现的扩展业务模块
utils    提供无状态、可复用的辅助能力
scripts  执行数据库迁移、种子数据等启动初始化任务
```

依赖方向应尽量保持为：业务模块依赖 `core/common/utils/config`，Controller 依赖 Service，Service 依赖 CRUD，CRUD 依赖 Model。`core` 不应直接承载具体业务规则。
