"""附件台账与新业务引用；上传生命周期由 upload.py 独立管理。"""
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.storage.node.model import StorageNodeModel
from app.utils.common_util import search_to_dict

from .crud import StorageFileCRUD
from .model import StorageFileModel, StorageFileReferenceModel
from .schema import StorageFileOutSchema, StorageFileQueryParam
from .utils import file_fingerprint, public_file_url


class AttachmentService:
    def __init__(self, auth: AuthSchema, db: AsyncSession, base_url: str = ""):
        self.auth, self.db, self.base_url = auth, db, base_url

    def _crud(self):
        return StorageFileCRUD(self.auth, self.db)

    async def _out_many(self, objects) -> list[StorageFileOutSchema]:
        if not objects:
            return []
        ids = [obj.id for obj in objects]
        nodes = (await self.db.scalars(select(StorageNodeModel).where(StorageNodeModel.id.in_({obj.storage_node_id for obj in objects})))).all()
        node_map = {node.id: node for node in nodes}
        counts = dict((await self.db.execute(select(StorageFileReferenceModel.file_id, func.count()).where(StorageFileReferenceModel.file_id.in_(ids)).group_by(StorageFileReferenceModel.file_id))).all())
        result = []
        for obj in objects:
            out = StorageFileOutSchema.model_validate({column.name: getattr(obj, column.name) for column in obj.__table__.columns})
            node = node_map.get(obj.storage_node_id)
            out.file_id = obj.id
            if node:
                out.storage_name = node.name
                out.protocol = node.protocol
                out.file_url = public_file_url(node, obj.file_path, self.base_url)
            out.reference_count = counts.get(obj.id, 0)
            result.append(out)
        return result

    async def page(self, search: StorageFileQueryParam, page_no: int, page_size: int, order_by=None):
        result = await self._crud().page(offset=(page_no - 1) * page_size, limit=page_size, order_by=order_by or [{"id": "desc"}], search=search_to_dict(search))
        return PageResultSchema[StorageFileOutSchema](page_no=result.page_no, page_size=result.page_size, total=result.total, has_next=result.has_next, items=await self._out_many(result.items))

    async def detail(self, id: int):
        obj = await self._crud().get_or_404(id=id)
        return (await self._out_many([obj]))[0]

    async def validate_reference(self, file_id: int, topic: str | None = None, *, user_id: int | None = None):
        # 用户归属独立于公有读取权限；业务服务传入自身服务端身份，禁止客户端自报 user_id。
        obj = await self.db.scalar(select(StorageFileModel).where(StorageFileModel.id == file_id, StorageFileModel.is_deleted.is_(False), StorageFileModel.status == 0).with_for_update())
        allowed = obj is not None and ((user_id is not None and obj.user_id == user_id) or (user_id is None and obj.admin_id == self.auth.user.id) or (user_id is None and self.auth.user.is_superuser))
        if not allowed or (topic and obj.topic != topic):
            raise CustomException(msg="附件不存在、已停用或无权引用")
        return obj

    async def replace_references(self, business_type: str, business_id: str, field: str, file_ids: list[int], topic: str | None = None, *, user_id: int | None = None):
        """仅供已完成业务授权的服务调用，业务表同时保存 file_id；不暴露任意业务绑定接口。"""
        if any(not value or len(value) > 64 for value in (business_type, str(business_id), field)):
            raise CustomException(msg="业务附件引用标识无效")
        for file_id in sorted(set(file_ids)):
            await self.validate_reference(file_id, topic, user_id=user_id)
        await self.db.execute(delete(StorageFileReferenceModel).where(StorageFileReferenceModel.business_type == business_type, StorageFileReferenceModel.business_id == str(business_id), StorageFileReferenceModel.field == field))
        self.db.add_all([StorageFileReferenceModel(file_id=id, business_type=business_type, business_id=str(business_id), field=field) for id in set(file_ids)])
        await self.db.flush()

    async def resolve_references(self, business_type: str, business_id: str, field: str) -> list[StorageFileOutSchema]:
        """业务完成读取授权后解析文件引用，用于详情展示；公有 URL 不等于绑定授权。"""
        objects = (await self.db.scalars(select(StorageFileModel).join(
            StorageFileReferenceModel, StorageFileReferenceModel.file_id == StorageFileModel.id,
        ).where(StorageFileReferenceModel.business_type == business_type,
                StorageFileReferenceModel.business_id == str(business_id),
                StorageFileReferenceModel.field == field,
                StorageFileModel.is_deleted.is_(False)).order_by(StorageFileModel.id))).all()
        return await self._out_many(objects)

    async def update_status(self, id: int, status: int):
        await self._crud().get_or_404(id=id)
        await self.db.execute(select(StorageFileModel.id).where(StorageFileModel.id == id).with_for_update())
        if status and await self.db.scalar(select(StorageFileReferenceModel.file_id).where(StorageFileReferenceModel.file_id == id).limit(1).with_for_update()):
            raise CustomException(msg="附件已被业务引用，不能停用")
        obj = await self.db.get(StorageFileModel, id)
        key = file_fingerprint(obj.storage_node_id, obj.admin_id, obj.user_id, obj.topic, obj.sha1, obj.file_size)
        canonical = await self.db.scalar(select(StorageFileModel.id).where(StorageFileModel.dedup_key == key))
        try:
            async with self.db.begin_nested():
                await self._crud().update(id=id, data={"status": status, "dedup_key": key if status == 0 and canonical in (None, id) else None})
        except IntegrityError as exc:
            raise CustomException(msg="相同文件已有可用附件，请刷新后重试") from exc

    async def delete(self, ids: list[int]):
        if not ids:
            raise CustomException(msg="请选择附件")
        for id in sorted(set(ids)):
            await self._crud().get_or_404(id=id)
            await self.db.execute(select(StorageFileModel.id).where(StorageFileModel.id == id).with_for_update())
            if await self.db.scalar(select(StorageFileReferenceModel.file_id).where(StorageFileReferenceModel.file_id == id).limit(1).with_for_update()):
                raise CustomException(msg="附件已被业务引用，不能删除")
        # 旧业务仍存 URL，逻辑删除保留实际文件，避免破坏旧引用。
        for id in sorted(set(ids)):
            obj = await self.db.get(StorageFileModel, id)
            obj.dedup_key = None
        await self._crud().delete(ids=ids)
