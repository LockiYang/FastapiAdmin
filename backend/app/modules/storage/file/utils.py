"""附件路径、指纹和常见位图头部元数据。"""
import hashlib
import json
import struct
from urllib.parse import quote, urljoin, urlsplit

from app.core.exceptions import CustomException
from app.modules.storage.node.model import StorageNodeModel


def file_fingerprint(node_id: int, admin_id: int | None, user_id: int | None, topic: str, sha1: str, size: int) -> str:
    values = [node_id, admin_id, user_id, topic, sha1, size]
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()


def public_file_url(node: StorageNodeModel, path: str, base_url: str) -> str:
    base = node.public_base_url
    if not base:
        raise CustomException(msg="存储节点未配置公有访问地址")
    # 本地根路径属于当前 ASGI 应用；request.base_url 包含 /api/v1 等挂载前缀。
    # 完整公有域名保持原义，已经包含应用前缀的路径也不重复拼接。
    app_path = urlsplit(base_url).path.rstrip("/")
    if base.startswith("/") and app_path and not (base == app_path or base.startswith(app_path + "/")):
        base = base.lstrip("/")
    return urljoin(base_url, base.rstrip("/") + "/") + quote(path, safe="/")


def image_metadata(path: str) -> tuple[int, int, str | None]:
    """读取常见位图头部，不解压图片，不将用户文件内容全部载入内存。"""
    with open(path, "rb") as stream:
        head = stream.read(32)
        if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 24:
            return *struct.unpack(">II", head[16:24]), "image/png"
        if head[:6] in (b"GIF87a", b"GIF89a") and len(head) >= 10:
            return *struct.unpack("<HH", head[6:10]), "image/gif"
        if head.startswith(b"\xff\xd8"):
            stream.seek(2)
            while marker := stream.read(1):
                if marker != b"\xff":
                    continue
                while marker == b"\xff":
                    marker = stream.read(1)
                if not marker or marker in (b"\xd9", b"\xda"):
                    break
                if marker == b"\x01" or 0xD0 <= marker[0] <= 0xD7:
                    continue
                raw = stream.read(2)
                if len(raw) != 2:
                    break
                length = int.from_bytes(raw, "big")
                if length < 2:
                    break
                if marker[0] in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                    raw = stream.read(5)
                    if len(raw) == 5:
                        height, width = struct.unpack(">HH", raw[1:])
                        return width, height, "image/jpeg"
                    break
                stream.seek(length - 2, 1)
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            if head[12:16] == b"VP8X" and len(head) >= 30:
                return int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1, "image/webp"
            if head[12:16] == b"VP8L" and len(head) >= 25 and head[20] == 0x2F:
                bits = int.from_bytes(head[21:25], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1, "image/webp"
            if head[12:16] == b"VP8 " and head[23:26] == b"\x9d\x01\x2a" and len(head) >= 30:
                width, height = struct.unpack("<HH", head[26:30])
                return width & 0x3FFF, height & 0x3FFF, "image/webp"
        if head[:2] == b"BM" and len(head) >= 26:
            width, height = struct.unpack("<ii", head[18:26])
            return abs(width), abs(height), "image/bmp"
        if head[:4] == b"\x00\x00\x01\x00" and len(head) >= 8:
            return head[6] or 256, head[7] or 256, "image/x-icon"
        if head.startswith(b"%PDF"):
            return 0, 0, "application/pdf"
    return 0, 0, None


