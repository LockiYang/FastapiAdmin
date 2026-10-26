# FastAPI 用户指南：20 分钟速览

基于 [FastAPI 中文用户指南](https://fastapi.tiangolo.com/zh/tutorial/) 整理。按写一个接口的顺序阅读；每节只保留入门开发最常用的知识，标注时间合计约 20 分钟。以下代码是**独立教学片段**，不是本仓库可直接粘贴的完整应用；本项目入口和分层见 [arch.md](../../docs/arch.md)。

先记住一条主线：**路由确定 URL 和方法 → 类型注解与 Pydantic 校验输入 → `Depends` 注入公共能力 → 业务代码处理数据 → 响应模型约束输出**。

## 1. 创建接口（约 2 分钟）

`FastAPI()` 创建应用；`@app.get/post/put/patch/delete("路径")` 把函数注册为接口。类型注解让 FastAPI 自动解析参数、校验输入并生成 OpenAPI 文档。

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"ok": True}
```

用 `async def` 调用支持 `await` 的数据库或 HTTP 客户端；调用同步阻塞库时可用普通 `def` 路由，避免在 `async def` 中直接阻塞事件循环。独立示例安装 `fastapi[standard]` 后可用 `fastapi dev` 启动；**本仓库**在 `backend/` 下运行 `uv run main.py run --env=dev`。接口文档通常在 `/docs`，原始规范在 `/openapi.json`；本项目配置了 `/api/v1` 根路径。[官方：第一步](https://fastapi.tiangolo.com/zh/tutorial/first-steps/) · [并发与 async/await](https://fastapi.tiangolo.com/zh/async/)

## 2. 路径、查询与校验（约 2 分钟）

路径里有 `{item_id}` 就是路径参数；函数中其余简单类型参数通常来自查询字符串。无默认值表示必填，`= None` 表示可不传。`Path`、`Query` 添加范围、长度等规则，校验失败由 FastAPI 返回 422。

```python
from typing import Annotated
from fastapi import Path, Query

@app.get("/items/{item_id}")
async def get_item(
    item_id: Annotated[int, Path(gt=0)],
    q: Annotated[str | None, Query(max_length=50)] = None,
):
    return {"id": item_id, "q": q}
```

`Annotated[类型, 附加信息]` 表示“参数是什么类型，以及 FastAPI 怎样读取或校验它”。上例中 `item_id` 从 URL 路径读取，`q` 从 `?q=...` 读取。`str | None` 表示值可以是 `None`；真正使 `q` 可以省略的是 `= None`。例：`GET /items/3?q=book`。固定路径（如 `/items/latest`）应注册在 `/items/{item_id}` 前。[官方：路径参数](https://fastapi.tiangolo.com/zh/tutorial/path-params/) · [查询参数](https://fastapi.tiangolo.com/zh/tutorial/query-params/) · [参数校验](https://fastapi.tiangolo.com/zh/tutorial/query-params-str-validations/)

## 3. JSON 请求体（约 2 分钟）

用 Pydantic `BaseModel` 描述 JSON；嵌套对象用嵌套模型，列表用 `list[模型]`。`Field` 定义字段约束。业务代码拿到的是已校验的对象，写库前可用 `model_dump()` 转字典。

```python
from pydantic import BaseModel, Field

class ItemIn(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    description: str | None = None

@app.post("/items")
async def create_item(item: ItemIn):
    return item.model_dump()
```

`PUT` 通常提交完整对象；`PATCH` 只改传入字段时，使用 `item.model_dump(exclude_unset=True)`，避免用默认值覆盖旧数据。[官方：请求体](https://fastapi.tiangolo.com/zh/tutorial/body/) · [更新数据](https://fastapi.tiangolo.com/zh/tutorial/body-updates/)

## 4. Header、Cookie、表单与文件（约 1 分钟）

普通 JSON 接口优先使用请求体模型。需要从其他位置取值时，使用 `Header()`、`Cookie()`、`Form()`；文件上传使用 `UploadFile` 与 `File()`，可异步读取，也可访问 `file.filename`。表单/文件使用 `multipart/form-data` 或表单编码，不能把同一次请求同时当作普通 JSON 请求体处理。

```python
from fastapi import File, UploadFile

@app.post("/upload")
async def upload(file: Annotated[UploadFile, File()]):
    return {"filename": file.filename}
```

[官方：Header](https://fastapi.tiangolo.com/zh/tutorial/header-params/) · [表单](https://fastapi.tiangolo.com/zh/tutorial/request-forms/) · [文件](https://fastapi.tiangolo.com/zh/tutorial/request-files/)

## 5. 响应、状态码与错误（约 2 分钟）

`response_model` 约束并过滤输出字段，尤其适合避免返回密码等内部数据。创建资源常用 201；找不到资源用 `raise HTTPException(404, ...)`。FastAPI 会根据返回值序列化 JSON，并在 `/docs` 展示模型和状态码。

```python
from fastapi import HTTPException

class ItemOut(BaseModel):
    id: int
    name: str
    price: float

@app.post("/items/new", response_model=ItemOut, status_code=201)
async def add_item(item: ItemIn):
    if item.name == "blocked":
        raise HTTPException(status_code=400, detail="名称不可用")
    return {"id": 1, **item.model_dump()}  # 额外字段由 response_model 过滤
```

常见 HTTP 状态：200 成功、201 创建、204 无响应体、400 请求不合业务规则、401 未认证、403 无权限、404 不存在、422 输入校验失败。[官方：响应模型](https://fastapi.tiangolo.com/zh/tutorial/response-model/) · [状态码](https://fastapi.tiangolo.com/zh/tutorial/response-status-code/) · [错误](https://fastapi.tiangolo.com/zh/tutorial/handling-errors/)

## 6. 依赖注入（约 2 分钟）

`Depends` 用于复用数据库会话、当前用户、分页参数等逻辑。`Annotated[int, Depends(get_page_size)]` 表示：参数是整数，其值由 FastAPI 调用 `get_page_size` 后提供。传入**函数本身**，不要写 `Depends(fn())`。依赖可以嵌套；同一请求中重复使用同一个依赖时，默认复用其结果。

```python
from fastapi import Depends

def get_page_size(size: Annotated[int, Query(ge=1, le=100)] = 20) -> int:
    return size

@app.get("/page")
async def list_page(size: Annotated[int, Depends(get_page_size)]):
    return {"size": size}
```

本项目的 `app/core/dependencies.py` 中，`db_getter()` 用 `yield` 提供请求级事务会话。[官方：依赖项](https://fastapi.tiangolo.com/zh/tutorial/dependencies/) · [`yield` 依赖](https://fastapi.tiangolo.com/zh/tutorial/dependencies/dependencies-with-yield/)

需要释放资源时，依赖使用 `yield`：先创建并交出资源，请求结束后在 `finally` 中清理。数据库 Session 是最常见的例子。

## 7. 登录与授权（约 2 分钟）

常见做法是登录后签发 Bearer JWT，请求携带 `Authorization: Bearer <token>`。`OAuth2PasswordBearer` 负责从请求提取令牌并描述 OpenAPI 安全方案；**令牌签名、有效期、用户状态和权限仍需自行校验**。密码只保存哈希，不保存明文。受保护接口把“获取当前用户”写成依赖，再叠加权限检查。[官方：JWT 教程](https://fastapi.tiangolo.com/zh/tutorial/security/oauth2-jwt/)

本项目额外使用 Redis 会话控制登录状态，认证实现见 `app/core/dependencies.py` 和 `app/modules/system/auth/`。

## 8. 多文件路由与中间件（约 2 分钟）

用 `APIRouter` 按业务域拆接口，再在应用中 `include_router()`；`prefix` 统一路径，`tags` 分组文档。中间件在路由前后处理横切逻辑；跨域用 `CORSMiddleware`，需要携带 Cookie 或 Authorization 时，明确列出允许的来源。[官方：多文件应用](https://fastapi.tiangolo.com/zh/tutorial/bigger-applications/) · [中间件](https://fastapi.tiangolo.com/zh/tutorial/middleware/) · [CORS](https://fastapi.tiangolo.com/zh/tutorial/cors/)

```python
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{user_id}")
async def read_user(user_id: int):
    return {"id": user_id}

app.include_router(router)
```

## 9. 数据库与生命周期（约 2 分钟）

FastAPI 不绑定 ORM。常见模式是：创建引擎和会话工厂 → 用 `yield` 依赖给每个请求提供会话 → 在 Service/CRUD 中查询或写入。输入、数据库、输出模型按需要分开，防止内部字段外泄。**修改 Python Model 不会自动修改已有数据库表**；表结构变化用迁移工具管理。应用启动/关闭时需要初始化与释放共享资源，可使用 `lifespan`。[官方：SQL 数据库](https://fastapi.tiangolo.com/zh/tutorial/sql-databases/) · [生命周期](https://fastapi.tiangolo.com/zh/advanced/events/)

本项目使用 SQLAlchemy 异步会话与 Alembic；不要在请求的事件循环内直接执行同步数据库 I/O。

## 10. 后台任务与实时响应（约 1 分钟）

`BackgroundTasks` 适合“先返回响应、随后做少量工作”，例如发通知；它在应用进程内运行，不能当成持久任务队列。服务端持续单向推送可用 SSE；客户端需要双向通信可用 WebSocket。[官方：后台任务](https://fastapi.tiangolo.com/zh/tutorial/background-tasks/) · [SSE](https://fastapi.tiangolo.com/zh/tutorial/server-sent-events/)

## 11. 测试与排查（约 2 分钟）

用 `TestClient` 像发 HTTP 请求一样测接口，至少断言状态码和关键响应字段。若测试依赖启动/关闭生命周期，用 `with TestClient(app) as client:`；需要替换数据库、认证等外部依赖时，用 `app.dependency_overrides`，测试结束后清理覆盖配置。排错时先检查 URL、HTTP 方法和参数来源，再查看 422 响应中的 `detail`。[官方：测试](https://fastapi.tiangolo.com/zh/tutorial/testing/)

```python
from fastapi.testclient import TestClient

def test_ping():
    with TestClient(app) as client:
        response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

**记忆顺序**：路由定义协议 → Pydantic 校验输入/输出 → Depends 注入共享能力 → Service/CRUD 处理业务与数据 → 测试验证行为。遇到具体需求再点击相应官方章节深读。
