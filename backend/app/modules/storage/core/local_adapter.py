import os
import shutil
from datetime import datetime
from pathlib import Path

from app.config.path_conf import BASE_DIR
from app.core.exceptions import CustomException
from app.core.logger import logger
from app.modules.storage.core.base import BaseStorageAdapter, StorageObject, StorageProtocol


class LocalStorageAdapter(BaseStorageAdapter):
    """本地磁盘/挂载目录存储适配器（零 SDK，同步调用经 asyncio.to_thread 包装）。"""

    protocol = StorageProtocol.LOCAL

    def __init__(self, config) -> None:
        super().__init__(config)
        self.root = str((BASE_DIR / (config.host or "")).resolve())

    def _abs_path(self, remote_path: str) -> str:
        """将远端相对路径映射为本地绝对路径，并防御路径穿越。

        remote_path 为相对存储真根（host 根目录）的路径，直接 join 到 root 下。
        """
        if ".." in remote_path:
            raise CustomException(msg="本地存储不允许路径穿越（..）")
        target = (Path(self.root) / remote_path.lstrip("/")).resolve()
        if not target.is_relative_to(Path(self.root)):
            raise CustomException(msg="本地路径不在存储根目录内")
        return str(target)

    def _sync_test_connection(self) -> bool:
        if not self.root or not os.path.isdir(self.root):
            logger.warning(f"本地存储根目录不可用: {self.root}")
            return False
        return os.access(self.root, os.R_OK | os.W_OK)

    def _sync_upload(self, local_path: str, remote_path: str, content_type: str | None = None) -> str:
        dest = self._abs_path(remote_path)
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(local_path, dest)
        except Exception:
            logger.exception('本地存储上传失败')
            raise
        return remote_path

    def _sync_download(self, remote_path: str, local_path: str) -> str:
        src = self._abs_path(remote_path)
        try:
            shutil.copy2(src, local_path)
        except Exception:
            logger.exception('本地存储下载失败')
            raise
        return local_path

    def _sync_delete(self, remote_path: str) -> None:
        target = self._abs_path(remote_path)
        try:
            Path(target).unlink(missing_ok=True)
        except Exception:
            logger.exception('本地存储删除失败')
            raise

    def _sync_exists(self, remote_path: str) -> bool:
        return os.path.exists(self._abs_path(remote_path))

    def _sync_list(self, prefix: str) -> list[StorageObject]:
        base_dir = self._abs_path(prefix) if prefix else self.root
        try:
            entries = os.scandir(base_dir)
        except OSError:
            logger.exception('本地存储列表失败')
            raise

        result: list[StorageObject] = []
        for entry in entries:
            try:
                is_dir = entry.is_dir()
                stat = entry.stat()
            except OSError:
                continue
            key = f"{prefix}/{entry.name}" if prefix else entry.name
            result.append(
                StorageObject(
                    name=entry.name,
                    key=key,
                    is_dir=is_dir,
                    size=None if is_dir else stat.st_size,
                    modified_time=datetime.fromtimestamp(stat.st_mtime),
                )
            )
        return result
