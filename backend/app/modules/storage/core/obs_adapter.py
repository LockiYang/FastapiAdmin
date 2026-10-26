from datetime import UTC, datetime
from typing import Any

from obs import ObsClient, UploadFileHeader

from app.core.exceptions import CustomException
from app.core.logger import logger
from app.modules.storage.core.base import (
    BaseStorageAdapter,
    ObsAdvancedConfig,
    StorageObject,
    StoragePage,
    StorageProtocol,
    normalize_endpoint,
)


class ObsStorageAdapter(BaseStorageAdapter):
    """华为云 OBS 适配器：上传、只读浏览/下载及单文件补偿删除。"""

    protocol = StorageProtocol.OBS

    def __init__(self, config) -> None:
        super().__init__(config)
        if not self.config.endpoint:
            raise CustomException(msg="OBS 存储源必须配置 endpoint")
        adv = ObsAdvancedConfig(**self.config.advanced_config)
        self.client = ObsClient(
            access_key_id=self.config.username or "",
            secret_access_key=self.config.password or "",
            server=normalize_endpoint(self.config.endpoint, self.config.scheme),
            is_secure=self.config.is_secure,
            max_retry_count=adv.max_retry_count,
            timeout=adv.timeout,
            ssl_verify=adv.ssl_verify,
            is_cname=adv.is_cname,
            path_style=adv.path_style,
            pool_size=adv.pool_size,
            signature=adv.signature,
            region=adv.region,
            security_token=adv.security_token,
        )

    @staticmethod
    def _is_ok(resp: Any) -> bool:
        """判断 OBS 响应是否成功（status < 300）。SDK 未提供类型存根，故用 getattr 访问动态属性。"""
        status = getattr(resp, "status", None)
        return status is not None and status < 300

    @staticmethod
    def _error_desc(resp: Any) -> str:
        """提取 OBS 响应中的错误描述。"""
        code = getattr(resp, "errorCode", "") or ""
        message = getattr(resp, "errorMessage", "") or ""
        return f"{code} {message}".strip()

    def _sync_test_connection(self) -> bool:
        try:
            resp = self.client.listBuckets()
            if self._is_ok(resp):
                resp = self.client.headBucket(bucketName=self._require_bucket())
                if self._is_ok(resp):
                    return True
            logger.warning(f"OBS 连接测试失败: {self._error_desc(resp)}")
            return False
        except Exception as e:
            logger.warning(f"OBS 连接测试失败: {e}")
            return False

    def _sync_upload(self, local_path: str, remote_path: str, content_type: str | None = None) -> str:
        """上传文件，按节点配置由 SDK 管理分片。"""
        try:
            part_size, concurrency = self._multipart_settings()
            resp = self.client.uploadFile(
                bucketName=self._require_bucket(),
                objectKey=remote_path,
                uploadFile=local_path,
                headers=UploadFileHeader(contentType=content_type),
                partSize=part_size,
                taskNum=concurrency,
                enableCheckpoint=True,
            )
            if not self._is_ok(resp):
                logger.error(f"OBS 上传失败: {self._error_desc(resp)}")
                raise RuntimeError(f"OBS 上传失败: {self._error_desc(resp)}")
        except CustomException:
            raise
        except Exception:
            logger.exception('OBS 上传失败')
            raise
        return remote_path

    def _sync_download(self, remote_path: str, local_path: str) -> str:
        """下载（downloadFile 断点续传 + 分片并发）。"""
        try:
            resp = self.client.downloadFile(
                bucketName=self._require_bucket(),
                objectKey=remote_path,
                downloadFile=local_path,
                partSize=5 * 1024 * 1024,
                taskNum=3,
                enableCheckpoint=True,
            )
            if not self._is_ok(resp):
                logger.error(f"OBS 下载失败: {self._error_desc(resp)}")
                raise RuntimeError(f"OBS 下载失败: {self._error_desc(resp)}")
        except CustomException:
            raise
        except Exception:
            logger.exception('OBS 下载失败')
            raise
        return local_path

    def _sync_delete(self, remote_path: str) -> None:
        try:
            resp = self.client.deleteObject(bucketName=self._require_bucket(), objectKey=remote_path)
            if not self._is_ok(resp):
                logger.error(f"OBS 删除失败: {self._error_desc(resp)}")
                raise RuntimeError(f"OBS 删除失败: {self._error_desc(resp)}")
        except CustomException:
            raise
        except Exception:
            logger.exception('OBS 下载失败')
            raise

    def _sync_exists(self, remote_path: str) -> bool:
        try:
            resp = self.client.getObjectMetadata(bucketName=self._require_bucket(), objectKey=remote_path)
            return self._is_ok(resp)
        except Exception:
            return False

    @staticmethod
    def _to_utc_dt(value: str | None) -> datetime | None:
        """OBS SDK 的 lastModified 为 UTC 字符串（如 '2026/08/25 09:25:27'），转为 aware datetime。"""
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y/%m/%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            return None

    def _sync_list(self, prefix: str) -> list[StorageObject]:
        """列举桶内“目录层”条目（Delimiter=/ 模拟文件夹，返回名称/是否目录/大小/修改时间）。
        OBS 单次最多返回 1000 条，经 marker 翻页拉全量。"""
        try:
            result: list[StorageObject] = []
            seen_dirs: set[str] = set()
            seen_files: set[str] = set()
            marker: str | None = None
            while True:
                kwargs: dict[str, Any] = {"bucketName": self._require_bucket(), "prefix": prefix, "delimiter": "/"}
                if marker:
                    kwargs["marker"] = marker
                resp = self.client.listObjects(**kwargs)
                if not self._is_ok(resp):
                    logger.error(f"OBS 列表失败: {self._error_desc(resp)}")
                    raise RuntimeError(f"OBS 列表失败: {self._error_desc(resp)}")
                body = getattr(resp, "body", None)
                for common in getattr(body, "commonPrefixs", None) or []:
                    raw_key = (getattr(common, "prefix", "") or "").rstrip("/")
                    if raw_key in seen_dirs:
                        continue
                    seen_dirs.add(raw_key)
                    result.append(StorageObject(name=raw_key.rsplit("/", 1)[-1], key=raw_key, is_dir=True))
                for obj in getattr(body, "contents", None) or []:
                    raw_key = getattr(obj, "key", "") or ""
                    if raw_key == prefix:
                        continue
                    name = raw_key.rsplit("/", 1)[-1]
                    if not name:  # key 以 "/" 结尾的目录占位对象，不按文件展示
                        continue
                    if raw_key in seen_files:
                        continue
                    seen_files.add(raw_key)
                    result.append(
                        StorageObject(
                            name=name,
                            key=raw_key,
                            is_dir=False,
                            size=getattr(obj, "size", None),
                            modified_time=self._to_utc_dt(getattr(obj, "lastModified", None)),
                        )
                    )
                if getattr(body, "is_truncated", None):
                    marker = getattr(body, "next_marker", None) or ""
                    if not marker:
                        break
                else:
                    break
            return result
        except CustomException:
            raise
        except Exception:
            logger.exception('OBS 列表失败')
            raise

    def _sync_list_page(self, prefix: str, page_size: int, cursor: str | None) -> StoragePage:
        """游标分页：单次 SDK 请求只拉一页（OBS marker），翻页经前端回传游标。"""
        try:
            kwargs: dict[str, Any] = {
                "bucketName": self._require_bucket(),
                "prefix": prefix,
                "delimiter": "/",
                "max_keys": page_size,
            }
            if cursor:
                kwargs["marker"] = cursor
            resp = self.client.listObjects(**kwargs)
            if not self._is_ok(resp):
                logger.error(f"OBS 列表失败: {self._error_desc(resp)}")
                raise RuntimeError(f"OBS 列表失败: {self._error_desc(resp)}")
            body = getattr(resp, "body", None)
            truncated = bool(getattr(body, "is_truncated", None))
            next_cursor = getattr(body, "next_marker", None) or None
            items: list[StorageObject] = []
            for common in getattr(body, "commonPrefixs", None) or []:
                raw_key = (getattr(common, "prefix", "") or "").rstrip("/")
                items.append(StorageObject(name=raw_key.rsplit("/", 1)[-1], key=raw_key, is_dir=True))
            for obj in getattr(body, "contents", None) or []:
                raw_key = getattr(obj, "key", "") or ""
                if raw_key == prefix:
                    continue
                name = raw_key.rsplit("/", 1)[-1]
                if not name:  # key 以 "/" 结尾的目录占位对象，不按文件展示
                    continue
                items.append(
                    StorageObject(
                        name=name,
                        key=raw_key,
                        is_dir=False,
                        size=getattr(obj, "size", None),
                        modified_time=self._to_utc_dt(getattr(obj, "lastModified", None)),
                    )
                )
            return StoragePage(
                items=items,
                has_next=truncated,
                next_cursor=next_cursor,
            )
        except CustomException:
            raise
        except Exception:
            logger.exception('OBS 列表失败')
            raise

    def _sync_list_buckets(self) -> list[str]:
        """列出账号下全部存储桶。"""
        try:
            resp = self.client.listBuckets()
            if not self._is_ok(resp):
                logger.error(f"OBS 桶列表失败: {self._error_desc(resp)}")
                raise RuntimeError(f"OBS 桶列表失败: {self._error_desc(resp)}")
            body = getattr(resp, "body", None)
            buckets = getattr(body, "buckets", None) or []
            return [getattr(b, "name", "") or "" for b in buckets if getattr(b, "name", "")]
        except CustomException:
            raise
        except Exception:
            logger.exception('OBS 桶列表失败')
            raise


    def _list_all_keys(self, prefix: str) -> list[str]:
        """分页列举前缀下的全部对象 key。"""
        keys: list[str] = []
        marker: str | None = None
        while True:
            kwargs: dict[str, Any] = {"bucketName": self._require_bucket(), "prefix": prefix}
            if marker:
                kwargs["marker"] = marker
            resp = self.client.listObjects(**kwargs)
            if not self._is_ok(resp):
                logger.error(f"OBS 列举对象失败: {self._error_desc(resp)}")
                raise RuntimeError(f"OBS 列举对象失败: {self._error_desc(resp)}")
            body = getattr(resp, "body", None)
            for obj in getattr(body, "contents", None) or []:
                key = getattr(obj, "key", "")
                if key:
                    keys.append(key)
            if not getattr(body, "is_truncated", False):
                break
            # 未指定 delimiter 时服务端可能不返回 next_marker，退化为当前页最后一个 key，避免死循环
            marker = getattr(body, "next_marker", None) or (keys[-1] if keys else "")
            if not marker:
                break
        return keys

    def _is_dir(self, key: str) -> bool:
        """判断 key 是否代表目录（存在占位对象或前缀下有任何对象）。"""
        try:
            resp = self.client.listObjects(bucketName=self._require_bucket(), prefix=key.rstrip("/") + "/", max_keys=1)
            if not self._is_ok(resp):
                return False
            body = getattr(resp, "body", None)
            return bool(getattr(body, "contents", None) or getattr(body, "commonPrefixs", None))
        except Exception:
            return False

    def _sync_list_recursive(self, prefix: str) -> list[StorageObject]:
        try:
            keys = self._list_all_keys(prefix)
        except Exception:
            logger.exception('OBS 递归列表失败')
            raise
        return self._entries_from_keys(keys)

    def _sync_close(self) -> None:
        """关闭 OBS 客户端连接。"""
        try:
            self.client.close()
        except Exception as e:
            logger.warning(f"OBS 关闭连接失败: {e}")
