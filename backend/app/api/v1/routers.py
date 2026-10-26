"""v1 路由总表：按 ENABLED_MODULES 注册可选业务路由。"""

from importlib import import_module

from fastapi import APIRouter

from app.config.setting import settings
from app.modules.common.file.controller import FileRouter
from app.modules.monitor.cache.controller import CacheRouter
from app.modules.monitor.health.controller import HealthRouter
from app.modules.monitor.online.controller import OnlineRouter
from app.modules.monitor.server.controller import ServerRouter
from app.modules.system.auth.controller import AuthRouter
from app.modules.system.dept.controller import DeptRouter
from app.modules.system.dict.controller import DictRouter
from app.modules.system.log.controller import LogRouter
from app.modules.system.menu.controller import MenuRouter
from app.modules.system.notice.controller import NoticeRouter
from app.modules.system.params.controller import ParamsRouter
from app.modules.system.position.controller import PositionRouter
from app.modules.system.role.controller import RoleRouter
from app.modules.system.ticket.controller import TicketRouter
from app.modules.system.user.controller import UserRouter
from app.modules.system.versions.controller import VersionRouter


def _optional_controllers(module: str, *paths: str) -> list[APIRouter]:
    if not settings.module_enabled(module):
        return []
    return [getattr(import_module(path), name) for path, name in (item.rsplit(":", 1) for item in paths)]

# 域前缀 → 该域 controller 清单（唯一路由事实来源）
DOMAIN_CONTROLLERS: dict[str, list[APIRouter]] = {
    "/system": [
        AuthRouter,
        UserRouter,
        RoleRouter,
        MenuRouter,
        DeptRouter,
        PositionRouter,
        DictRouter,
        ParamsRouter,
        NoticeRouter,
        TicketRouter,
        VersionRouter,
        LogRouter,
    ],
    "/monitor": [
        CacheRouter,
        HealthRouter,
        OnlineRouter,
        ServerRouter,
    ],
    "/task": [
        *_optional_controllers(
            "task",
            "app.modules.task.job.controller:CronJobRouter",
            "app.modules.task.node.controller:CronJobNodeRouter",
        ),
        *_optional_controllers(
            "storage",
            "app.modules.storage.browse.controller:StorageBrowseRouter",
            "app.modules.storage.node.controller:StorageNodeRouter",
            "app.modules.storage.file.controller:StorageAttachmentRouter",
        ),
    ],
    "/generator": _optional_controllers("generator", "app.modules.generator.gencode.controller:GenRouter"),
    "/common": [FileRouter],
}

api_v1 = APIRouter()
for prefix, controllers in DOMAIN_CONTROLLERS.items():
    if not controllers:
        continue
    router = APIRouter(prefix=prefix)
    for controller in controllers:
        router.include_router(controller)
    api_v1.include_router(router)
