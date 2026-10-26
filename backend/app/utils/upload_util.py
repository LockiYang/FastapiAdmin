
from fastapi import UploadFile

from app.config.setting import settings
from app.core.exceptions import CustomException

DANGEROUS_EXTENSIONS = {
    ".py",
    ".pyc",
    ".pyo",
    ".php",
    ".php3",
    ".php4",
    ".php5",
    ".phtml",
    ".exe",
    ".bat",
    ".cmd",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".ps2",
    ".psm1",
    ".psd1",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".wsf",
    ".wsh",
    ".msi",
    ".dll",
    ".so",
    ".dylib",
    ".jar",
    ".class",
    ".jsp",
    ".jspx",
    ".asp",
    ".aspx",
    ".asa",
    ".asax",
    ".cer",
    ".cdx",
    ".config",
    ".htaccess",
    ".htpasswd",
    ".sql",
    ".db",
    ".sqlite",
    ".sqlite3",
}

class UploadUtil:
    """上传工具类
    """

    @staticmethod
    def check_path_traversal(filename: str) -> bool:
        """检查文件名是否包含路径穿越。

        参数:
        - filename (str): 文件名。

        返回:
        - bool: 是否安全（True 表示安全，False 表示存在路径穿越）。
        """
        dangerous_patterns = ["../", "..\\", "/", "\\", "\0"]
        for pattern in dangerous_patterns:
            if pattern in filename:
                return False
        return True

    @staticmethod
    def get_extension_from_filename(filename: str) -> str:
        """从文件名获取扩展名。

        参数:
        - filename (str): 文件名。

        返回:
        - str: 扩展名（小写，包含点），如 ".jpg"。
        """
        if not filename or "." not in filename:
            return ""
        ext = filename.rsplit(".", 1)[-1].lower()
        return f".{ext}" if ext else ""

    @staticmethod
    def is_dangerous_extension(extension: str) -> bool:
        """检查扩展名是否为危险类型。

        参数:
        - extension (str): 文件扩展名。

        返回:
        - bool: 是否为危险扩展名。
        """
        return extension.lower() in DANGEROUS_EXTENSIONS

    @classmethod
    def validate_file_extension(cls, extension: str) -> bool:
        """验证文件扩展名是否在允许列表中。

        参数:
        - extension (str): 文件扩展名。

        返回:
        - bool: 是否允许。

        异常:
        - CustomException: 扩展名不允许时抛出。
        """
        ext_lower = extension.lower()
        if cls.is_dangerous_extension(ext_lower):
            raise CustomException(msg=f"不允许上传此类型的文件: {extension}")
        if ext_lower not in settings.ALLOWED_EXTENSIONS:
            raise CustomException(msg=f"文件类型不支持，允许的类型: {', '.join(settings.ALLOWED_EXTENSIONS)}")
        return True

    @staticmethod
    def check_file_size(file: UploadFile) -> bool:
        """校验文件大小是否合法。

        参数:
        - file (UploadFile): 上传的文件对象。

        返回:
        - bool: 文件大小是否合法。

        异常:
        - CustomException: 文件过大时抛出。
        """
        if file.size and file.size > settings.MAX_FILE_SIZE:
            raise CustomException(msg=f"文件大小超过限制，最大允许 {settings.MAX_FILE_SIZE // (1024 * 1024)}MB")
        return True
