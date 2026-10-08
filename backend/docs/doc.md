# 根目录与 Backend 的 AI 文档，以及它们如何配合 AI Coding

> DSH 协作手册与历史审计报告现统一归档在根目录 `dsh/`。下文第 1–4 节保留原审计时的组织说明；当前文件位置以第 5.2 节链接为准。

第 1–4 节覆盖仓库**根目录**和 **`backend/`** 里、会被 AI Coding（单会话编码、子任务委派、多智能体团队）读取或产出的文档。第 5 节为 **2026-10-08 全仓库多智能体协作文件盘点**，补充前端、部署、隐藏目录和业务代码，区分直接协作规则、团队交付物、通用 AI 技能与业务 Agent/Team。

这些文档分成四类角色：

| 角色 | 文档 | 在 AI Coding 里做什么 |
| --- | --- | --- |
| 操作手册 | 根 `SKILL.md` | 开工前对齐目录、命令、分层约定和已踩过的坑 |
| 组队纪律 | `dsh/TEAM-PLAYBOOK.md` | 决定单会话还是组队，以及审计波 / 交付波怎么分工、怎么验收 |
| 规格与知识 | 根 `REQUIREMENTS.md`；`backend/docs/prd.md`、`arch.md`、`fastapi.md`、`basics.md`；`backend/README.md` | 告诉模型「要做什么」和「代码该长什么样」 |
| 证据与约束 | `dsh/AUDIT-REPORT.md`、`DEPLOYMENT.md`、`README.md`、`CONTRIBUTING.md`、`CHANGELOG.md`；`dsh/backend/audit-*.md` | 记录已核实的问题、不可逆动作和对外说明，避免下一轮编码把旧结论当事实或擅自上线 |

人读的总览和 AI 读的操作手册是分开的。`README.md` 面向克隆后五分钟跑起来；`SKILL.md` 面向写代码前的约定。两者可以同时被模型读到，但改业务代码时以 `SKILL.md` 和 `backend/docs/` 为准。

---

## 1. 根目录文档与现已归档到 `dsh/` 的文档

### 1.1 `SKILL.md` — 全栈开发技能

文件头是技能元数据：`name: fastapiadmin-dev`。描述要求在本仓库写代码、建模块或页面、调试、构建或跑测试之前先调用它。

它给模型的是可执行约定，而不是产品介绍：

- 工程地图：`backend/`、`frontend/web/`、`frontend/app/`、`frontend/docs/`、`docker/` 各自的技术栈和入口
- 后端模块固定文件：`controller.py` / `service.py` / `crud.py` / `model.py` / `schema.py`，路由在 `app/api/v1/routers.py` 注册，权限标识是 `模块:资源:操作`
- 前端 Web 套件：`useTable`、`FaTable`、`v-hasPerm`、动态菜单、KeepAlive 与 WebSocket 的清理方式
- 验证命令：后端 `uv run pytest`；前端 `pnpm ts:check`、`pnpm lint`、`pnpm test`
- 已发生过的失败模式：静态前端目录检查与挂载路径不一致、Jinja2 `{% set %}` 作用域、dist 产物未同步导致线上仍跑旧包

单会话 AI Coding 的默认路径是：先按这份技能对齐，再改代码，再跑技能里写的验证命令。

### 1.2 `dsh/TEAM-PLAYBOOK.md` — 多智能体协作纪律

本文件只写**本仓库和本机团队插件没有自动提供**的部分。通用策略（显式委派才建团队、共享工作目录、任务范围协调等）由运行时注入，这里不重复。

按 `dsh/TEAM-PLAYBOOK.md` 的历史记录，DeepSeek DSH 团队栈使用第三方插件 `@nanmicoder/dsh-agent-teams`（工具族 `agent_teams_*`，斜杠命令 `/agent-teams`）。状态约定落在工作区 `.agent-teams/`（已 gitignore）。该手册记录官方实验包于 2026-10-05 从当时的本机 profile 移除，避免「工具用一套、面板看另一套」。这些是手册记载的环境信息，不代表当前 Codex 会话已安装该插件；本次检查也未发现根目录 `.agent-teams/`。

开工第一步是看当前会话实际有哪些委派工具，再选档位：

| 档位 | 什么时候用 |
| --- | --- |
| 单会话直接做 | 单文件、改动很小、需求明确 |
| 子任务 / fork | 独立小任务，或需要带上本会话上下文 |
| workflow | 几十个互不依赖的同类单元 |
| 团队（Agent Teams） | 多角色并行探索，并且要质量门禁和可追溯记录 |

判据是任务能否切成互不重叠的单元。能并行探索就组队；只能串行改同一批文件，就退回「1 个实现 + 1 个复核」。

两种队形：

- **审计波（只读，5–7 人）**：后端架构、前端、测试、安全、运维、产品、UX/UI。每人一个 `kind=work` 任务，产出「文件:行号 + 证据 + 优先级」。任务说明里写明不得改代码、不得启服务或装依赖、不得提交 git。队长汇总，并修正成员的错误表述。成员结论是材料。
- **交付波（3–4 人）**：`implementation`（必要时 `repair`）→ `review`（`verdict=pass`）→ 必要时 `integration`。实现任务必须写全 `objective` / `acceptance` / `verify` / `inScope` / `outOfScope`。复核失败会自动加 repair 和下一轮 review。跨端大改先审计、归档，再开交付波。

本项目里反复出过、写进 playbook 的约束：

- `inScope` 必须逐文件，目录型条目对不上完成态校验
- 质量/复核任务必须显式指定 `assignee`，否则可能把后端复核派给前端
- 并行任务按文件边界切开；两个任务碰同一文件就要串行
- `verify` 命令先在本地跑通；`acceptance` 不得引用仓库里不存在的用例
- review 通过之外，还要独立做类型检查、测试或线上实测
- 部署、合并到 master、推送远端、轮换凭据、删除团队必须人确认。部署只走 `./deploy-artifacts.sh`；推送只推 `origin`

Playbook 第 7 节的审计波模板直接对应下面这些报告文件名，避免多个成员写进同一个文件。

### 1.3 `REQUIREMENTS.md` — 目标规格（SaaS 多租户）

标题是「SaaS 多租户平台需求文档」，版本 v3.6.0（2026-06-03），约 3100 行。内容覆盖租户隔离、套餐、平台/租户/用户三层权限，以及 Tenant、Package、Plugin、工单、AI Chat、代码生成等模块的目标行为。

`SKILL.md` 把它列为做大功能前要读的需求。审计波里的产品角色以它为基线，对照三端代码，产出 `dsh/backend/audit-requirements.md`。

它描述的是目标产品，不是当前仓库的行为。`dsh/backend/audit-requirements.md` 与 `dsh/AUDIT-REPORT.md` 已核实：三端代码里没有 `tenant` 实现，该文件来自一次纯文档提交。AI Coding 若把它当成「现在已经这样工作」，会按不存在的租户模型改代码。当前已实现的后端行为以 `backend/docs/prd.md` 为准；`REQUIREMENTS.md` 只作为差距和未来范围。

### 1.4 `dsh/AUDIT-REPORT.md` — 审计波的队长总报告

2026-10-04 由 7 名审计成员并行审查后，由队长汇总并做线上复核。它把各分报告收成一份可执行结论：blocker / high 问题、需求与实现的错位、本轮已修项、仍须人工决定的项，并指回 `dsh/TEAM-PLAYBOOK.md`。

对后续 AI Coding，它是「已知事实清单」：下一轮实现或复核应先看这里和对应分报告，避免重复发现，也避免把已经轮换过的密钥、已经改过的部署面再当成当前缺陷。

### 1.5 给人读、同时约束 AI 的根文档

| 文件 | AI Coding 里怎么用 |
| --- | --- |
| `README.md` / `README.en.md` | 克隆、默认账号、端口、模块开关、Docker 一键部署的对外说明。`SKILL.md` 与 `backend/README.md` 都指向它。种子口令是公开的，安全审计把它当成风险，不能在新环境里照抄当生产口令。 |
| `CONTRIBUTING.md` | 贡献入口：Issue、本地三端启动、PR 进 `dev`、提交前 `ruff check` / `pnpm lint`。 |
| `DEPLOYMENT.md` | 阿里云单机 Docker 的运维手册。和 playbook 的不可逆动作对齐：本机构建成品，服务器只收镜像和静态产物。 |
| `CHANGELOG.md` | 显著变更记录。查「某次重构改了哪」时用它，不用它代替代码。 |

---

## 2. `backend/` 文档与现已归档的审计报告

### 2.1 `docs/prd.md` — 与代码对齐的后端产品需求

开篇写明：业务范围以本文件为准；接口行为以 `backend/app/` 里的 Controller、Schema、Service、Model 核对。文末「核对来源」把根 `REQUIREMENTS.md` 标成需求背景，把 `routers.py`、各模块源码和 `base_crud` / `permission` / `dependencies` 标成实际契约。

AI 改后端接口、权限或数据范围时读这份，而不是通读 3000 行的 `REQUIREMENTS.md`。它按业务域写规则和路径：系统、任务与存储、AI 聊天与代码生成、监控，并给出表索引。

### 2.2 `docs/arch.md` — 后端技术架构

说明单体 FastAPI 如何分层，以及一次请求怎么走完：

`客户端 →（Docker 时）Nginx → FastAPI → Controller → Service → CRUD → MySQL/PostgreSQL/SQLite、Redis、对象存储或 AI 模型`

同时写清启动顺序（`create_app`、迁移与种子、Agno 会话表、Redis、调度器）和目录依赖方向：业务模块依赖 `core/common/utils/config`，Controller 依赖 Service，Service 依赖 CRUD，`core` 不承载具体业务规则。

模型要决定「新代码放哪、请求链上谁负责校验和事务」时读它。`fastapi.md` 和 `basics.md` 都指向这里，避免教学片段被当成仓库入口。

### 2.3 `docs/fastapi.md` — FastAPI 速览

按写一个接口的顺序压缩官方教程：路由、校验、请求体、依赖注入、授权、中间件、生命周期、SSE/WebSocket、测试。文内示例是独立教学片段，并反复注明本仓库的启动命令是 `uv run main.py run --env=dev`，项目分层见 `arch.md`。

`basics.md` 开头写「FastAPI 路由和依赖注入先读 tutorial.md」。仓库里没有 `tutorial.md`，对应文件就是本篇 `fastapi.md`。

### 2.4 `docs/basics.md` — 本项目版本下的四件套

只覆盖在本仓库里开始开发需要的 SQLAlchemy 2.0、Alembic 1.18、Pydantic 2、APScheduler 3，并且落到本项目文件：`base_model.py`、`base_crud.py`、`alembic`、`setting.py`、`ap_scheduler.py`。最后一节把四者串成新增功能的顺序：Schema 校验 → Service → Model/Session → Alembic → 需要时才加定时任务。

模型和 `SKILL.md` 第 3 节一起用：技能说「改了 model 必须做迁移」，这篇说迁移命令和检查 `upgrade()` / `downgrade()` 时要看什么。

### 2.5 `README.md` — 后端目录与命令

声明项目总览、演示账号和 Docker 以根 `README.md` 为准；本文档只管 `backend/` 的目录、模块分层、`uv sync`、`main.py run/revision/upgrade` 和 ruff。日期序列化约定（`DateTimeStr`、`model_dump(mode='json')`）也在这里，生成或手写 Schema 时要遵守。

### 2.6 `dsh/backend/audit-*.md` — 审计波分报告

这些文件现存放于 `dsh/backend/`，是团队审计的产物，格式统一为只读、带命令退出码、结论落到 `文件:行号`。

| 文件 | 对应 playbook 角色 | 内容 |
| --- | --- | --- |
| `audit-backend.md` | 后端架构师 | 架构与代码质量；含 pytest / ruff 的真实退出码，以及当时无法连上的数据库端口 |
| `audit-security.md` | 安全审计员 | 认证、授权、敏感信息；与 `dsh/docker/audit-deploy.md` 交叉引用，不重复展开部署链 |
| `audit-testing.md` | 测试工程师 | 测试是否真能失败、CI 是否会跑；并指出 `SKILL.md` 里的 pytest / 前端 test 当时没有自动执行点 |
| `audit-requirements.md` | 产品（需求覆盖） | `REQUIREMENTS.md` 与三端实现的差距，结论是多租户规格在代码中零实现 |

同一次审计还在原 `backend/` 目录之外写了 `dsh/frontend/audit-frontend.md`、`dsh/frontend/audit-uxui.md`、`dsh/docker/audit-deploy.md`。`dsh/AUDIT-REPORT.md` 是这七份的汇总。后续编码把分报告当证据，把总报告当优先级；报告里的行号是审计当时的行号，改代码前要重新打开源文件核对。

---

## 3. 和 AI Coding 的协作方式

### 3.1 单会话：技能 + 后端文档

一次小改动的阅读顺序：

1. `SKILL.md`：确认改的是哪个端、文件该放哪、权限标识和验证命令是什么。
2. 只动后端时补读 `backend/docs/arch.md`（放哪一层）和 `backend/docs/prd.md`（这个接口现在的规则）。
3. 要写路由、模型、迁移或定时任务时，再读 `fastapi.md` / `basics.md`，避免用过时的 FastAPI 或 SQLAlchemy 1.x 写法。
4. 改完按 `SKILL.md` 与 playbook 第 4 节的命令验证。Playbook 给出的后端命令是 `UV_CACHE_DIR=/tmp/uv-cache-test uv run --no-sync pytest -q` 和同样前缀的 `ruff check`，用于沙箱写不了默认 uv 缓存的环境。

`SKILL.md` 第 5 节的「新增一个业务功能」把后端文档里的分层收成六步：建模块 → 注册路由 → 迁移并配置菜单 → 前端 API 与页面 → 前后端权限标识一致 → pytest 与前端检查。

### 3.2 审计波：playbook 规定产出，文档变成下一轮输入

```text
dsh/TEAM-PLAYBOOK.md §7 模板
        │  create：7 名只读成员，各自一份报告
        ▼
dsh/backend/audit-backend.md
dsh/backend/audit-security.md
dsh/backend/audit-testing.md
dsh/backend/audit-requirements.md
dsh/frontend/audit-frontend.md
dsh/frontend/audit-uxui.md
dsh/docker/audit-deploy.md
        │  队长修正错误表述、补线上实测
        ▼
dsh/AUDIT-REPORT.md
        │  下一轮单会话或交付波先读
        ▼
按优先级改代码，改完用 playbook 的验证命令复跑
```

产品成员读 `REQUIREMENTS.md`，对照源码写 `audit-requirements.md`。后端成员读 `arch.md` / `prd.md` 不足以代替读代码：审计要求证据是文件和行号，架构文档只帮助定位。队长不把成员原文直接当结论。

### 3.3 交付波：规格进任务，复核对着验收标准

实现任务从 `prd.md`（当前行为）和 `SKILL.md`（怎么写才符合仓库）取出范围，写成 `objective` / `acceptance` / `verify` / `inScope` / `outOfScope`。`inScope` 用具体文件，便于完成态核对 `changedPaths`。

复核任务显式指定负责人，并用 `reviewedTaskId` 指向被复核任务。通过复核之后，队长仍按 playbook 自己复跑关键命令。类型检查、测试、线上实测至少做两项。部署、推送、轮换凭据不由模型自行完成，见 `dsh/TEAM-PLAYBOOK.md` 第 5 节和 `DEPLOYMENT.md`。

### 3.4 文档之间不要混用的三处

1. **两份需求**：`REQUIREMENTS.md` 是 SaaS 多租户目标规格；`backend/docs/prd.md` 是当前后端实现。实现任务以 `prd.md` 和源码为准。若任务是补齐多租户，才以 `REQUIREMENTS.md` 为范围，并先确认产品要立项。
2. **两套验证命令**：`SKILL.md` 写日常命令（`uv run pytest`、`pnpm ts:check`）。`dsh/TEAM-PLAYBOOK.md` 写团队在受限环境下能跑通的命令（`UV_CACHE_DIR` + `--no-sync`，以及前端 `pnpm run type-check`，且 Web 类型检查前要先 `pnpm run build:prod`，因为 `src/types/*.d.ts` 不入库）。审计报告记录的是当时那一次的退出码。
3. **教学片段与仓库代码**：`fastapi.md`、`basics.md` 里的短示例用于对齐 API 心智；粘贴进仓库前要改成项目的 `SuccessResponse`、`AuthPermission`、`CRUDBase` 和 `uv run main.py` 入口，这些在 `SKILL.md` 与 `arch.md`。

---

## 4. 建议的读取顺序

| 你要做的事 | 先读 | 再读 |
| --- | --- | --- |
| 改一个明确的小功能 | `SKILL.md` | `backend/docs/prd.md`、`arch.md` |
| 新增后端模块或改表 | `SKILL.md` §3、§5 | `basics.md`、`backend/README.md` |
| 只想搞清 FastAPI / ORM 在本项目里怎么写 | `fastapi.md` | `basics.md`、`arch.md` |
| 判断该不该组队 | `dsh/TEAM-PLAYBOOK.md` §1–§2 | 审计波模板 §7 |
| 接着上一轮审计改缺陷 | `dsh/AUDIT-REPORT.md` | 对应的 `dsh/backend/audit-*.md`，再打开源文件核对行号 |
| 部署或推远端 | `DEPLOYMENT.md` | `dsh/TEAM-PLAYBOOK.md` §5（须人确认） |
| 评估多租户要不要做 | `audit-requirements.md` 的结论 | `REQUIREMENTS.md` 相关章节 |

---

## 5. 全仓库多智能体协作文件盘点（2026-10-08）

### 5.1 结论与检索范围

项目中的 AI Coding 多智能体协作主要由 **1 份协作手册、1 份审计总报告、7 份分报告，以及 Git 忽略规则**体现。它们记录的是 DeepSeek DSH 开发团队的协作流程，并非项目业务后端实现的团队调度系统。

本次使用 `rg --files --hidden` 和全文搜索核对根目录、`backend/`、`frontend/`、`docker/`、`.github/` 及可见隐藏文件；关键词包括 `多智能体`、`agent-teams`、`subagent`、`teammate`、`DSH`、`审计成员`、`队长`、`reviewedTaskId`、`changedPaths`、`agno.team`。排除 `.git`、依赖安装目录、虚拟环境、构建产物和锁文件噪声。另按路径检查了根目录的 AI 配置与团队状态目录是否存在。

本次只核对文件用途与协作关联，未重跑历史报告中的测试、部署或安全验证。下表的行号为本次检查时的定位信息，后续文件变化后应按内容重新定位。

### 5.2 直接涉及 AI Coding 多智能体协作的文件

| 文件 | 证据位置 | 关联内容与用途 |
| --- | --- | --- |
| [dsh/TEAM-PLAYBOOK.md](../../dsh/TEAM-PLAYBOOK.md) | 第 1、11–21、35–73、97–148 行 | 核心协作规则：DSH 插件栈、工具探测、单会话/子任务/团队选择、审计波和交付波、文件范围分工、复核与修复、验收、归档，以及七角色任务模板。 |
| [dsh/AUDIT-REPORT.md](../../dsh/AUDIT-REPORT.md) | 第 5、174、232–234 行 | 七名成员并行审计的总交付物；记录实现、修复、复审过程及团队归档，并链接协作手册。 |
| [dsh/backend/audit-backend.md](../../dsh/backend/audit-backend.md) | 文件开头；手册 §7 的 `a1` 模板 | 后端架构师的分报告；记录后端架构、代码质量、检查结果和未验证项。 |
| [dsh/backend/audit-testing.md](../../dsh/backend/audit-testing.md) | 第 1–6、508–510 行 | 明确记录测试工程师、team `fastapiadmin-audit`、task `t3`；说明其他 teammate 的并行产物使工作区在审计开始时已含改动。 |
| [dsh/backend/audit-security.md](../../dsh/backend/audit-security.md) | 第 3–9 行 | 安全成员任务 `t4` 的分报告；定义只读边界、证据规则，并交叉引用运维任务 `t6`。 |
| [dsh/backend/audit-requirements.md](../../dsh/backend/audit-requirements.md) | 文件开头；手册 §7 的 `a6` 模板 | 产品/需求覆盖角色的分报告；把需求规格与三端代码进行映射。 |
| [dsh/frontend/audit-frontend.md](../../dsh/frontend/audit-frontend.md) | 文件开头；手册 §7 的 `a2` 模板 | 前端角色的分报告；覆盖 Web 和移动端，后端只作为接口契约参照。 |
| [dsh/frontend/audit-uxui.md](../../dsh/frontend/audit-uxui.md) | 文件开头；手册 §7 的 `a7` 模板 | UX/UI 角色的分报告；记录静态证据、未执行的浏览器/真机检查及验证缺口。 |
| [dsh/docker/audit-deploy.md](../../dsh/docker/audit-deploy.md) | 第 3、114、301、429、775 行 | 运维任务 `t6` 的分报告；提到团队状态进入构建上下文的风险，以及并行成员改文件造成证据行号变化。 |
| [.gitignore](../../.gitignore) | 第 72–78 行 | 忽略 `CLAUDE.md`、`AGENTS.md`、`.codebuddy`、`.agent`、`.workbuddy`；第 77–78 行明确把 `.agent-teams/` 标为本地协作运行期状态。忽略规则不等于这些文件已存在。 |
| [backend/docs/doc.md](doc.md) | §1.2、§2.6、§3.2–§3.3、§5 | 文档索引与本次盘点结果，串联规则、任务产物和下一轮开发输入；本身不运行团队。 |

模板中的 `a1`–`a7` 是可复制的示例任务 ID，报告中的 `t3`、`t4`、`t6` 等是历史任务 ID，两者不要当成同一组 ID。

### 5.3 为协作提供输入，但不负责多智能体调度的文档

| 文件或目录 | 在协作中提供什么 | 与团队机制的关系 |
| --- | --- | --- |
| [SKILL.md](../../SKILL.md) | 工程地图、分层、代码约定、验证命令和常见问题。 | 单个 AI 和多个 AI 都可读取；没有创建团队或分配任务的实现。 |
| [REQUIREMENTS.md](../../REQUIREMENTS.md) | 目标产品规格；需求成员的审计基线。 | 作为任务输入，不能代替当前源码事实。 |
| [backend/docs/prd.md](prd.md)、[arch.md](arch.md)、[fastapi.md](fastapi.md)、[basics.md](basics.md) | 后端行为、架构和开发知识。 | 帮助成员理解任务；不是团队插件配置。 |
| [DEPLOYMENT.md](../../DEPLOYMENT.md)、[CONTRIBUTING.md](../../CONTRIBUTING.md) | 部署和贡献流程。 | 提供交付约束，不执行成员协调。 |
| [frontend/docs/src/guide/guidelines.md](../../frontend/docs/src/guide/guidelines.md) | 团队开发、提交、测试和 Code Review 规范。 | 通用开发协作规范，不能仅凭“团队”字样判为多智能体协议。 |
| [frontend/docs/src/guide/why.md](../../frontend/docs/src/guide/why.md)、[overview.md](../../frontend/docs/src/guide/overview.md)、[about/about.md](../../frontend/docs/src/about/about.md) | 业务模块边界、低耦合与多人开发的说明。 | 描述架构对协作的帮助，没有智能体调度规则。 |
| `frontend/app/.agents/skills/` | `create-wot-ui-theme`、`wot-ui-v2`、`starter-cleaner`、`wot-ui-unocss-preset-guide`、`wot-ui-cli` 五项技能及其支持文件。 | 面向 AI 的移动端开发技能；目录名含 `.agents` 不代表会启动多个智能体。 |

README、CHANGELOG 等也可被成员作为背景读取，但没有因此被列为直接多智能体协作文件。依赖名称中的 `agent-base`、`http-proxy-agent`、`https-proxy-agent` 属于网络代理依赖，不是 AI 开发团队。

### 5.4 业务中的 Agno Agent/Team：与开发团队区分

| 文件 | 证据位置 | 实际职责 |
| --- | --- | --- |
| [backend/app/utils/ai_factory.py](../app/utils/ai_factory.py) | 第 3–5、56–80 行 | `AgnoFactory.create_agent()` 创建 Agno `Agent` 和 `Team`，供产品的 AI 聊天使用。当前 `members=[fastapiadmin_agent]` 只有一个成员，且该成员 `tools=[]`；不能据此认定已实现多个编码智能体协作。 |
| [backend/app/modules/ai/chat/service.py](../app/modules/ai/chat/service.py) | 第 9–10、171、222–229 行 | 使用 Team 会话和运行结果，调用工厂创建聊天实例并运行模型。 |
| [backend/app/modules/ai/chat/crud.py](../app/modules/ai/chat/crud.py) | 第 11、21、163–170 行 | Agno `TeamSession` 的数据库访问、创建和会话标识管理。 |
| [backend/docs/arch.md](arch.md)、[prd.md](prd.md) | `arch.md` 第 50 行；`prd.md` §5.1 | 介绍产品的 AI 聊天、模型配置与会话存储。 |

这组代码属于应用功能，不负责 DSH 的成员创建、任务板、文件写入范围或代码复核门禁。前端 AI 聊天页面和接口同样属于产品功能。

### 5.5 当前工作区状态及文档时效

- **存在**：`dsh/TEAM-PLAYBOOK.md`、审计总报告和七份分报告、`.gitignore` 中的团队状态忽略规则，以及移动端 `.agents/skills/`。
- **根目录未发现**：`AGENTS.md`、`.agent-teams/`、`.agent/`、`.agents/`、`.codex/`、`.codebuddy/`、`.workbuddy/`。这仅说明本次工作区没有这些路径，不能证明其他机器没有，也不能证明团队插件是否已安装。
- **仓库外引用**：手册中的 `cordis.patch.yml`、profile 配置、插件 `README_ZH.md`、`.generations/live/` 和 DeepSeek 实验包路径属于 DSH 宿主环境，未在本次项目文件检查中验证。插件版本、成员上限、移除记录都应按历史记载理解。
- **构建忽略规则**：当前根 [.dockerignore](../../.dockerignore) 未显式排除 `.agent-teams/`。运维审计曾记录此问题；本次只记录规则现状，未验证实际构建上下文或镜像是否包含团队状态。
- **跨工具使用**：文件分工、独立复核、验收证据等原则可以用于 Codex；`agent_teams_*`、`/agent-teams`、`reviewedTaskId` 及插件自动修复循环属于原 DSH 插件协议，需要按当前宿主提供的工具适配，不能直接视为 Codex 能力。
