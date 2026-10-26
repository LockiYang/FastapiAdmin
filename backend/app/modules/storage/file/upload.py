"""统一上传：读取节点快照 -> 无数据库事务的文件 I/O -> 短事务登记，失败在本模块补偿。"""
import asyncio
import hashlib
import mimetypes
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.config.setting import settings
from app.core.base_schema import AuthSchema, UploadResponseSchema
from app.core.database import async_db_session
from app.core.exceptions import CustomException
from app.core.logger import logger
from app.modules.storage.core.factory import StorageAdapterFactory
from app.modules.storage.node.model import StorageNodeModel
from app.modules.storage.node.service import StorageNodeService
from app.utils.upload_util import UploadUtil

from .model import StorageFileModel
from .utils import file_fingerprint, image_metadata, public_file_url

TOPICS = frozenset({"file", "avatar", "param", "resource", "attachment"})


class UploadService:
    def __init__(self, auth: AuthSchema, base_url: str):
        self.auth, self.base_url = auth, base_url

    def _result(self, obj: StorageFileModel, node: StorageNodeModel) -> UploadResponseSchema:
        return UploadResponseSchema(file_id=obj.id, file_path=obj.file_path, file_name=obj.file_name,
            origin_name=obj.origin_name, file_url=public_file_url(node, obj.file_path, self.base_url),
            file_size=obj.file_size, mime_type=obj.mime_type, width=obj.width, height=obj.height)

    @staticmethod
    async def _cleanup(adapter, key: str) -> None:
        try:
            await adapter.delete(key)
        except Exception:
            logger.exception("上传补偿清理失败，需核对存储节点中的对象 {}", key)

    async def upload(self, file: UploadFile, topic: str = "file", *, user_id: int | None = None) -> UploadResponseSchema:
        if not settings.module_enabled("storage"):
            raise CustomException(msg="存储模块未启用")
        admin_id = None if user_id is not None else self.auth.user.id
        if (user_id is not None and user_id <= 0) or (user_id is None and not admin_id):
            raise CustomException(msg="上传需要有效用户身份")
        if topic not in TOPICS:
            raise CustomException(msg="不支持的附件分类")
        if not file.filename or len(file.filename) > 255 or not UploadUtil.check_path_traversal(file.filename):
            raise CustomException(msg="文件名称无效或过长")
        extension = UploadUtil.get_extension_from_filename(file.filename)
        UploadUtil.validate_file_extension(extension)
        if extension in {".html", ".htm", ".svg", ".xml"}:
            raise CustomException(msg="公有附件不允许上传活跃页面或 SVG/XML 文件")
        UploadUtil.check_file_size(file)
        fd, temp_path = tempfile.mkstemp(suffix=extension)
        os.close(fd)
        adapter = None
        uploaded_key = None
        committed = False
        try:
            digest = hashlib.sha1()
            size = 0
            async with aiofiles.open(temp_path, "wb") as stream:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.MAX_FILE_SIZE:
                        raise CustomException(msg="文件大小超过上传限制")
                    digest.update(chunk)
                    await stream.write(chunk)
            if size == 0:
                raise CustomException(msg="不能上传空文件")
            width, height, detected = await asyncio.to_thread(image_metadata, temp_path)
            expected = mimetypes.guess_type("file" + extension)[0]
            mime = detected or expected or "application/octet-stream"
            aliases = {"image/x-icon": "image/vnd.microsoft.icon"}
            if detected and aliases.get(detected, detected) != aliases.get(expected, expected):
                raise CustomException(msg="文件内容与扩展名不匹配")
            if mime.startswith("image/") and (width <= 0 or height <= 0):
                raise CustomException(msg="图片头部无效或格式不受支持")
            if topic == "avatar" and not mime.startswith("image/"):
                raise CustomException(msg="头像仅支持图片")
            sha1 = digest.hexdigest()
            # 快照选择本次节点；之后切换默认仅影响后续上传，不中断本次 I/O。
            async with async_db_session() as db:
                node_service = StorageNodeService(self.auth, db)
                node = await node_service.get_default_source()
                config = node_service.build_config(node)
                signature = node_service.location_signature(node)
                fingerprint = file_fingerprint(node.id, admin_id, user_id, topic, sha1, size)
                existing = await db.scalar(select(StorageFileModel).where(StorageFileModel.dedup_key == fingerprint))
                existing_id, existing_path = (existing.id, existing.file_path) if existing else (None, None)
                db.expunge(node)
            adapter = StorageAdapterFactory.create(config)
            exists = bool(existing_path and await adapter.exists(existing_path))
            if exists:
                async with async_db_session() as db, db.begin():
                    current_node = await self._check_node(db, node.id, signature)
                    obj = await db.scalar(select(StorageFileModel).where(StorageFileModel.dedup_key == fingerprint,
                        StorageFileModel.status == 0, StorageFileModel.is_deleted.is_(False)).with_for_update())
                    if obj is not None:
                        await self._reuse(db, obj)
                        result = self._result(obj, current_node)
                    else:
                        result = None
                if result is not None:
                    return result
            now = datetime.now(UTC)
            name = uuid4().hex + extension
            key = "/".join(filter(None, [(node.path_prefix or "").strip("/"), topic, now.strftime("%Y/%m/%d"), name]))
            if len(key) > 512:
                raise CustomException(msg="文件存储路径过长")
            uploaded_key = key  # 先登记本次对象，部分上传失败也需要补偿。
            await adapter.upload(temp_path, key, mime)
            # 远端 I/O 已结束，节点行锁只覆盖配置复核和记录提交。
            async with async_db_session() as db, db.begin():
                current_node = await self._check_node(db, node.id, signature)
                if existing_id is not None and not exists:
                    await db.execute(update(StorageFileModel).where(StorageFileModel.id == existing_id,
                        StorageFileModel.dedup_key == fingerprint).values(dedup_key=None))
                obj = StorageFileModel(topic=topic, admin_id=admin_id, user_id=user_id, storage_node_id=node.id,
                    file_path=key, file_name=name, origin_name=file.filename, file_size=size, mime_type=mime,
                    width=width, height=height, sha1=sha1, dedup_key=fingerprint, upload_count=1,
                    last_upload_time=now, created_id=admin_id, updated_id=admin_id, status=0)
                try:
                    async with db.begin_nested():
                        db.add(obj)
                        await db.flush()
                except IntegrityError:
                    # 同指纹并发写入只保留一个台账，其他唯一约束错误仍向外抛出。
                    obj = await db.scalar(select(StorageFileModel).where(StorageFileModel.dedup_key == fingerprint).with_for_update())
                    if obj is None:
                        raise
                    await self._reuse(db, obj)
                result = self._result(obj, current_node)
                kept_new_object = obj.file_path == key
            committed = True
            if not kept_new_object:
                await self._cleanup(adapter, key)
            return result
        except BaseException:
            if uploaded_key is not None and not committed and adapter is not None:
                await self._cleanup(adapter, uploaded_key)
            raise
        finally:
            try:
                if adapter is not None:
                    try:
                        await adapter.close()
                    except Exception:
                        logger.exception("关闭上传存储连接失败")
            finally:
                Path(temp_path).unlink(missing_ok=True)
                await file.seek(0)

    @staticmethod
    async def _check_node(db, id: int, signature: tuple) -> StorageNodeModel:
        if db.bind.dialect.name == "sqlite":
            # SQLite 无行级 FOR UPDATE；只在登记阶段获取短写锁。
            await db.execute(update(StorageNodeModel).where(StorageNodeModel.id == id).values(id=id))
        node = await db.scalar(select(StorageNodeModel).where(StorageNodeModel.id == id).with_for_update())
        if node is None or node.is_deleted or StorageNodeService.location_signature(node) != signature:
            raise CustomException(msg="上传期间存储位置已改变，请重新上传")
        StorageNodeService.validate_public_source(node)
        return node

    @staticmethod
    async def _reuse(db, obj: StorageFileModel) -> None:
        await db.execute(update(StorageFileModel).where(StorageFileModel.id == obj.id).values(
            upload_count=StorageFileModel.upload_count + 1, last_upload_time=datetime.now(UTC)))
        await db.refresh(obj)
