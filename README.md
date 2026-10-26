## 💡 为什么选择 FastapiAdmin？

| 你需要的 | FastapiAdmin | Django Admin | 纯前端模板 |
|---------|:-----------:|:-----------:|:---------:|
| 🎯 **开箱即用**的后台系统 | ✅ | ⚠️ 功能有限 | ❌ 只有 UI |
| ⚡ **FastAPI 异步**高性能后端 | ✅ | ❌ 同步为主 | ❌ 无后端 |
| 🔐 **RBAC** 菜单/按钮/数据三级权限 | ✅ | ❌ 基础 | ❌ |
| 🤖 **代码生成器**（选表 → 出前后端代码） | ✅ | ❌ | ❌ |
| 📱 **移动端**（H5 + 小程序）一体 | ✅ | ❌ | ❌ |
| 🐳 **Docker 一键部署**（含 Nginx + SSL） | ✅ | ❌ | ❌ |

## 🍪 在线体验

| 端 | 地址 | 账号 |
|----|------|------|
| 💻 Web 端 | [service.fastapiadmin.com/web](https://service.fastapiadmin.com/web) | `admin` / `123456` |
| 📱 移动端 | [service.fastapiadmin.com/app](https://service.fastapiadmin.com/app) | `admin` / `123456` |

## 🚀 5 分钟本地跑起来

```bash
# 1. 克隆
git clone https://gitee.com/fastapiadmin/FastapiAdmin.git

# 2. 配置环境
cp backend/env/.env.example backend/env/.env.dev
cp frontend/web/.env.development.example frontend/web/.env.development

# 3. 启动后端（首次自动建表 + 初始化数据）
cd backend && uv sync && uv run main.py run --env=dev
uv sync --extra mysql && uv run --extra mysql main.py run --env=dev

# 4. 启动前端
cd ../frontend/web && pnpm install && pnpm run dev

# ✅ 浏览器打开 http://127.0.0.1:5173，用 admin/123456 登录
```

| 环境要求 | |
|---------|------|
| Python ≥ 3.12 | Node.js ≥ 20.0 + pnpm |
| MySQL 8.0+ / PostgreSQL 14+ | Redis 6.x / 7.x |

Mysql建库语句

```
CREATE DATABASE IF NOT EXISTS `fastapiadmin`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;
```

### 🐳 或者：Docker 一键部署

```bash
cp docker/.env.example docker/.env    # 填写 MySQL / Redis 密码
./deploy.sh                           # 自动构建镜像并启动全栈（含 Nginx + SSL）
```

> 端口、SSL 证书、前端构建等细节见 [Docker 部署文档](docker/README.md)。

## 📦 工程结构

```
FastapiAdmin/            # Monorepo 全栈工程
├─ backend/              # FastAPI 后端（Pydantic 2.0 + SQLAlchemy + Alembic）
├─ frontend/
│   ├── web/             # Vue3 Web 前端（Element Plus + TypeScript）
│   └── app/             # UniApp 移动端（H5 + 小程序 + App）
├─ docker/               # Docker Compose 一键部署（Nginx + SSL）
├─ deploy.sh             # 一键部署脚本
└─ LICENSE               # MIT 开源协议
```

## 📌 内置功能

> **200+ REST 接口** · MySQL / PostgreSQL / SQLite 三方言 · SFTP / S3 / OSS / COS / OBS 五种存储协议 · `ENABLED_MODULES` 一行开关裁剪模块

### 核心模块（始终启用，不可裁剪）

| 模块 | 包含能力 |
|------|---------|
| 📊 仪表盘 | 工作台、数据分析 |
| ⚙️ 系统管理 | 用户 / 角色 / 菜单 / 部门 / 岗位 / 字典 / 参数 / 公告 / 工单 / 版本 |
| 👀 监控管理 | 在线用户 / 服务器监控 / 缓存监控 |
| 📝 日志管理 | 操作日志审计 |
| 🧰 开发工具 | 接口文档 |

### 扩展模块（可用 `ENABLED_MODULES` 裁剪）

| 模块 | 包含能力 | 裁剪开关 |
|------|---------|---------|
| 🧩 定时任务 | 定时任务调度与任务节点 | `task` |
| 🔧 代码生成器 | 选表 → 生成前后端全量代码 | `generator` |
| 📁 数据存储 | 存储源、文件浏览、传输任务与流程编排（SFTP / S3 / OSS / COS / OBS） | `storage` |
| 🤖 AI 对话 | 基于 Agno 的智能体对话 | `ai` |
| 💬 内部聊天（规划中） | 系统内用户**纯文字**私聊 / 群聊（WebSocket 实时推送 + 未读角标） | `chat`（尚未接入裁剪开关） |

## 🔧 模块裁剪

已实现的扩展模块可通过 `backend/app/config/setting.py` 中的 `ENABLED_MODULES` 按需启用 / 停用。默认启用 `generator`、`task`、`storage`、`ai`。停用模块的接口、运行时初始化和导航菜单不会加载或显示，已有数据库表与菜单数据会保留。`chat` 为规划项，目前加入列表不会启用内部聊天：

```python
# 默认配置；task 和 storage 可以分别移除
ENABLED_MODULES = ["generator", "task", "storage", "ai"]
```

## 🚦 部署说明

- **内部聊天范围**：规划为纯文字私聊 / 群聊；当前 `fastlink/fachat` 是本地模拟页面，尚无对应的服务端消息接口。
- **页面与接口路径**：侧边栏页面分别位于 `/task/`*、*`/storage/`；后端 API 路径分别为 `/task/cronjob/`*、`/task/storage/*`。
- **单实例部署**：定时任务调度器涉及本地调度与共享状态；多实例部署需确认调度锁、任务执行与状态同步符合预期。
- **密钥安全**：所有第三方密钥（AI、云存储等）请配置在 `backend/env/.env.`* 环境变量中，**切勿提交到仓库或写入数据库**。
- **数据库迁移**：正式环境请使用 Alembic 迁移（`uv run alembic upgrade head`）管理表结构变更，`create_all` 仅用于首次初始化的兜底。

## 📖 文档地址

- 📖 [架构说明](backend/docs/arch.md) · [业务规则](backend/docs/prd.md)
- 📁 子工程 README：[backend](backend/README.md) · [web](frontend/web/README.md) · [移动端](frontend/app/README.md) · [Docker](docker/README.md)

## 🙏 鸣谢

> 如果你觉得项目有用，请给一个 ⭐️ Star 支持！

- 后端：[FastAPI](https://fastapi.tiangolo.com/) · [Pydantic](https://docs.pydantic.dev/) · [SQLAlchemy](https://www.sqlalchemy.org/) · [APScheduler](https://github.com/agronholm/apscheduler)
- 前端：[Vue3](https://cn.vuejs.org/) · [TypeScript](https://www.typescriptlang.org/) · [Vite](https://vitejs.dev/) · [Element Plus](https://element-plus.org/)
- 移动端：[UniApp](https://uniapp.dcloud.net.cn/) · [Wot Design Uni](https://wot-ui.cn/)
- AI：[Agno](https://github.com/agno-agi/agno)
