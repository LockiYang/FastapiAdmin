from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.storage.core.base import (
    DEFAULT_PORTS,
    StorageAdapterConfig,
    StorageProtocol,
    decrypt_password,
    encrypt_password,
)
from app.modules.storage.core.factory import StorageAdapterFactory
from app.utils.common_util import search_to_dict

from .crud import StorageNodeCRUD
from .model import StorageNodeModel, StorageSettingModel
from .schema import StorageNodeCreateSchema, StorageNodeOutSchema, StorageNodeQueryParam, StorageNodeTestSchema, StorageNodeUpdateSchema


class StorageNodeService:
    """存储源管理服务"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    # ── 内部工具 ────────────────────────────────────────────────────

    def _crud(self) -> StorageNodeCRUD:
        return StorageNodeCRUD(self.auth, self.db)

    async def _default_id(self) -> int | None:
        return await self.db.scalar(select(StorageSettingModel.default_node_id).where(StorageSettingModel.id == 1))

    @staticmethod
    def _to_out(obj: StorageNodeModel, default_id: int | None) -> StorageNodeOutSchema:
        out = StorageNodeOutSchema.model_validate(obj)
        out.has_password = bool(obj.password)
        out.is_default = obj.id == default_id
        return out

    async def _lock_setting(self) -> StorageSettingModel:
        # 写锁也覆盖 SQLite；单例行由初始化/迁移建立。
        await self.db.execute(update(StorageSettingModel).where(StorageSettingModel.id == 1).values(id=1))
        setting = await self.db.get(StorageSettingModel, 1, populate_existing=True)
        if setting is None:
            raise CustomException(msg="存储设置尚未初始化，请先完成数据库迁移")
        return setting

    async def set_default(self, id: int) -> StorageNodeOutSchema:
        setting = await self._lock_setting()
        obj = await self._crud().get_or_404(id=id)
        await self.db.refresh(obj, with_for_update=True)
        self.validate_public_source(obj)
        setting.default_node_id = id
        await self.db.flush()
        return self._to_out(obj, await self._default_id())

    @staticmethod
    def validate_public_source(obj) -> None:
        if obj.status != 0:
            raise CustomException(msg="默认存储节点必须启用")
        if obj.protocol not in {"local", "s3", "oss", "cos", "obs"}:
            raise CustomException(msg="默认上传仅支持本地和对象存储")
        if not obj.public_base_url:
            raise CustomException(msg="请配置默认存储节点的公有访问根地址")
        if obj.protocol != "local" and obj.public_base_url.startswith("/"):
            raise CustomException(msg="对象存储必须配置完整的 HTTP/HTTPS 公有地址")

    async def get_default_source(self) -> StorageNodeModel:
        # 系统配置查询不受上传人的部门数据范围过滤；凭据仅在内部使用。
        node_id = await self._default_id()
        obj = await self.db.get(StorageNodeModel, node_id) if node_id else None
        if obj is None or obj.is_deleted:
            raise CustomException(msg="未设置默认存储节点")
        self.validate_public_source(obj)
        return obj

    @staticmethod
    def location_signature(source) -> tuple:
        """决定实际存储位置与公有链接的配置；凭据和性能选项可独立更新。"""
        fields = ("protocol", "host", "port", "bucket", "endpoint", "region", "scheme", "path_prefix", "public_base_url", "is_secure")
        advanced = source.advanced_config or {}
        routing = ("endpoint", "appid", "use_cname", "is_cname", "use_path_style", "path_style", "addressing_style", "region")
        return tuple(getattr(source, field) for field in fields) + tuple(advanced.get(key) for key in routing)

    @staticmethod
    def _build_config_from(source: Any, password: str) -> StorageAdapterConfig:
        """从 ORM 或表单对象构造适配器配置（password 为明文，统一处理端口/高级配置）。"""
        return StorageAdapterConfig(
            protocol=StorageProtocol(source.protocol),
            host=source.host,
            port=source.port or DEFAULT_PORTS[StorageProtocol(source.protocol)],
            username=source.username,
            password=password,
            bucket=source.bucket,
            endpoint=source.endpoint,
            scheme=source.scheme,
            region=source.region,
            is_secure=source.is_secure,
            implicit_tls=source.implicit_tls,
            encrypt_type=source.encrypt_type,
            connection_mode=source.connection_mode,
            encoding=source.encoding,
            multipart_part_size=source.multipart_part_size,
            multipart_concurrency=source.multipart_concurrency,
            multipart_memory_budget=source.multipart_memory_budget,
            advanced_config=source.advanced_config or {},
        )

    @staticmethod
    def build_config(obj: StorageNodeModel) -> StorageAdapterConfig:
        return StorageNodeService._build_config_from(obj, decrypt_password(obj.password))

    # ── 查询 ────────────────────────────────────────────────────────

    async def detail(self, id: int) -> StorageNodeOutSchema:
        obj = await self._crud().get_or_404(id=id)
        return self._to_out(obj, await self._default_id())

    async def page(
        self,
        search: StorageNodeQueryParam | None,
        page_no: int,
        page_size: int,
        order_by: list[dict] | None = None,
    ) -> PageResultSchema[StorageNodeOutSchema]:
        result = await self._crud().page(
            offset=(page_no - 1) * page_size,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search),
        )
        default_id = await self._default_id()
        return PageResultSchema[StorageNodeOutSchema](
            page_no=result.page_no,
            page_size=result.page_size,
            total=result.total,
            has_next=result.has_next,
            items=[self._to_out(obj, default_id) for obj in result.items],
        )

    async def get_list(self, search: StorageNodeQueryParam | None = None) -> list[StorageNodeOutSchema]:
        objs = await self._crud().get_list(search=search_to_dict(search), order_by=[{"id": "asc"}])
        default_id = await self._default_id()
        return [self._to_out(obj, default_id) for obj in objs]

    # ── 写入 ────────────────────────────────────────────────────────

    async def create(self, data: StorageNodeCreateSchema) -> StorageNodeOutSchema:
        exist = await self._crud().get(name=data.name)
        if exist:
            raise CustomException(msg="创建失败，存储源名称已存在")

        payload = data.model_dump(exclude_none=True)
        if payload.get("password"):
            payload["password"] = encrypt_password(payload["password"])

        obj = await self._crud().create(data=payload)
        return self._to_out(obj, await self._default_id())

    async def update(self, id: int, data: StorageNodeUpdateSchema) -> StorageNodeOutSchema:
        setting = await self._lock_setting()
        old = await self._crud().get_or_404(id=id, msg="更新失败，该存储源不存在")
        await self.db.refresh(old, with_for_update=True)
        if setting.default_node_id == id and data.status != 0:
            raise CustomException(msg="请先将其他节点设为默认，再停用或取消当前默认节点")
        from app.modules.storage.file.model import StorageFileModel
        has_files = await self.db.scalar(select(StorageFileModel.id).where(StorageFileModel.storage_node_id == id).limit(1).with_for_update())
        if has_files and self.location_signature(old) != self.location_signature(data):
            raise CustomException(msg="节点已有附件，不能修改存储位置或公有地址，请新建节点")
        if setting.default_node_id == id:
            self.validate_public_source(data)
        exist = await self._crud().get(name=data.name)
        if exist and exist.id != id:
            raise CustomException(msg="更新失败，存储源名称已存在")

        # 不用 exclude_none：None 表示用户清空可选字段（description/path_prefix/region 等），需落库为 NULL
        payload = data.model_dump(exclude_unset=True)
        if payload.get("password"):
            payload["password"] = encrypt_password(payload["password"])
        else:
            payload.pop("password", None)  # 未传新密码则不修改

        await self._crud().update(id=id, data=payload)
        obj = await self._crud().get_or_404(id=id)
        return self._to_out(obj, await self._default_id())

    async def delete(self, ids: list[int]) -> None:
        if not ids:
            raise CustomException(msg="删除失败，删除对象不能为空")
        setting = await self._lock_setting()
        from app.modules.storage.file.model import StorageFileModel
        for id in ids:
            await self._crud().get_or_404(id=id)
            if setting.default_node_id == id:
                raise CustomException(msg="默认节点不能删除，请先切换默认节点")
            if await self.db.scalar(select(StorageFileModel.id).where(StorageFileModel.storage_node_id == id).limit(1).with_for_update()):
                raise CustomException(msg="节点已有附件，不能删除")
        await self._crud().delete(ids=ids)

    # ── 连接测试 ────────────────────────────────────────────────────

    async def test_connection(self, id: int) -> bool:
        obj = await self._crud().get_or_404(id=id, msg="该存储源不存在")
        adapter = StorageAdapterFactory.create(self.build_config(obj))
        try:
            ok = await adapter.test_connection()
        finally:
            await adapter.close()
        if not ok:
            raise CustomException(msg="连接失败，请检查存储源配置")
        return True

    async def test_config(self, data: StorageNodeTestSchema) -> bool:
        """使用表单提交的配置直接测试连接（不落库），密码留空且传 source_id 时回退已保存密码。"""
        password = data.password or ""
        if not password and data.node_id:
            obj = await self._crud().get_or_404(id=data.node_id, msg="该存储源不存在")
            password = decrypt_password(obj.password)
        adapter = StorageAdapterFactory.create(self._build_config_from(data, password))
        try:
            ok = await adapter.test_connection()
        finally:
            await adapter.close()
        if not ok:
            raise CustomException(msg="连接失败，请检查存储源配置")
        return True

    # ── 供文件模块复用 ──────────────────────────────────────────────

    async def get_active_source(self, source_id: int | None = None) -> StorageNodeModel:
        """浏览指定节点仍检查管理数据范围；缺省严格使用默认节点。"""
        if source_id is None:
            source_id = await self._default_id()
        if source_id is None:
            raise CustomException(msg="未设置默认存储节点")
        source = await self._crud().get_or_404(id=source_id)
        if source.status != 0:
            raise CustomException(msg="该存储源已停用")
        return source
