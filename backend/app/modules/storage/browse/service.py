import asyncio
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.storage.core.base import (
    _OBJECT_STORE_PROTOCOLS,
    BaseStorageAdapter,
    StorageAdapterConfig,
    StorageObject,
    StoragePage,
)
from app.modules.storage.core.factory import StorageAdapterFactory
from app.modules.storage.node.service import StorageNodeService


class StorageBrowseService:
    """存储实际内容的只读浏览和下载服务"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    # ── 内部工具 ────────────────────────────────────────────────────

    @staticmethod
    def _validate_remote_path(remote_path: str) -> str:
        """规范化并校验远端相对路径（禁止路径穿越）。"""
        if not remote_path or not remote_path.strip():
            raise CustomException(msg="请提供文件路径")
        parts = [p for p in remote_path.replace("\\", "/").split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts) or "\x00" in remote_path:
            raise CustomException(msg="非法的文件路径")
        return "/".join(parts)

    async def _get_source(self, source_id: int | None) -> StorageAdapterConfig:
        """获取存储源并构造适配器配置（密码已解密，含 SDK 高级配置）。"""
        source = await StorageNodeService(self.auth, self.db).get_active_source(source_id)
        return StorageNodeService.build_config(source)

    async def _get_adapter(self, source_id: int | None, bucket: str | None = None) -> BaseStorageAdapter:
        """构造适配器并切换当前操作桶（对象存储多桶浏览：桶随请求传入，适配器按请求创建）。"""
        config = await self._get_source(source_id)
        adapter = StorageAdapterFactory.create(config)
        if bucket:
            adapter.set_bucket(bucket)
        return adapter

    @staticmethod
    def _zip_directory(src_root: Path, zip_path: str, arc_root: Path) -> None:
        """把 src_root 下所有文件打包到 zip_path（相对于 arc_root 计算归档名）。

        ZIP_DEFLATED 是纯 CPU + 磁盘 IO 的同步操作，目录较大时会在事件循环里
        独占数秒，因此统一由调用方通过 asyncio.to_thread 在线程中执行。
        """
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in src_root.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(arc_root).as_posix())

    # ── 业务方法 ────────────────────────────────────────────────────

    async def download(self, source_id: int | None, remote_path: str, bucket: str | None = None) -> tuple[str, str]:
        """下载远端文件到临时目录，返回 (本地临时路径, 文件名)。"""
        target = self._validate_remote_path(remote_path)
        extension = Path(target).suffix
        fd, temp_path = tempfile.mkstemp(suffix=extension)
        os.close(fd)
        adapter = await self._get_adapter(source_id, bucket)
        try:
            local_path = await adapter.download(target, temp_path)
        except Exception:
            os.unlink(temp_path)
            raise
        finally:
            await adapter.close()
        return local_path, Path(target).name

    async def download_dir(self, source_id: int | None, remote_path: str, bucket: str | None = None) -> tuple[str, str]:
        """递归下载目录并打包 ZIP，返回 (zip临时路径, zip文件名)。"""
        target = self._validate_remote_path(remote_path)
        adapter = await self._get_adapter(source_id, bucket)
        tmp_root = tempfile.mkdtemp(prefix="stor_dir_")
        zip_path = ""
        try:
            dir_name = Path(target).name or "download"
            local_dir = Path(tmp_root) / dir_name
            local_dir.mkdir(parents=True, exist_ok=True)
            await adapter.download_dir(target, str(local_dir), concurrency=3)
            fd, zip_path = tempfile.mkstemp(suffix=".zip")
            os.close(fd)
            await asyncio.to_thread(self._zip_directory, local_dir, zip_path, Path(tmp_root))
        except Exception:
            if zip_path:
                os.unlink(zip_path)
            raise
        finally:
            await adapter.close()
            await asyncio.to_thread(shutil.rmtree, tmp_root, ignore_errors=True)
        return zip_path, f"{dir_name}.zip"

    async def list_files(
        self,
        source_id: int | None,
        prefix: str = "",
        bucket: str | None = None,
        page_size: int | None = None,
        cursor: str | None = None,
    ) -> list[StorageObject] | StoragePage:
        """列出目录条目。

        - 不传 page_size：全量拉取（目录选择器/搜索等场景）。
        - 传 page_size：游标分页（对象存储走 SDK 原生游标，FTP/SFTP/LOCAL 走内存切片）。
        """
        safe_prefix = self._validate_remote_path(prefix) if prefix else ""
        adapter = await self._get_adapter(source_id, bucket)
        try:
            if page_size is not None:
                return await adapter.list_files(safe_prefix, page_size=page_size, cursor=cursor)
            return await adapter.list_files(safe_prefix)
        finally:
            await adapter.close()

    async def list_buckets(self, source_id: int | None) -> list[str]:
        """列出账号下全部存储桶（仅对象存储协议；FTP/SFTP/LOCAL 无桶概念返回空列表）。"""
        config = await self._get_source(source_id)
        if config.protocol not in _OBJECT_STORE_PROTOCOLS:
            return []
        adapter = StorageAdapterFactory.create(config)
        try:
            return await adapter.list_buckets()
        finally:
            await adapter.close()
