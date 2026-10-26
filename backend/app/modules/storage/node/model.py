from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import MappedBase, ModelMixin, UserMixin


class StorageNodeModel(ModelMixin, UserMixin):
    """存储源配置模型"""

    __tablename__: str = "task_storage_node"
    __table_args__: dict[str, str] = {"comment": "存储源配置表"}

    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="存储源名称")
    protocol: Mapped[str] = mapped_column(String(16), nullable=False, index=True, comment="协议(ftp/ftps/sftp/s3/obs/oss/cos/local)")
    host: Mapped[str | None] = mapped_column(String(255), default=None, nullable=True, comment="主机地址（对象存储可不填，用 endpoint）")
    port: Mapped[int] = mapped_column(Integer, nullable=False, comment="端口号（FTP/FTPS/SFTP 用）")
    username: Mapped[str | None] = mapped_column(String(255), default=None, nullable=True, comment="用户名/AccessKey")
    password: Mapped[str | None] = mapped_column(Text, default=None, nullable=True, comment="密码/SecretKey(Fernet加密)")
    bucket: Mapped[str | None] = mapped_column(String(255), default=None, nullable=True, comment="桶名（对象存储专用）")
    endpoint: Mapped[str | None] = mapped_column(String(255), default=None, nullable=True, comment="接入点(对象存储)")
    region: Mapped[str | None] = mapped_column(String(64), default=None, nullable=True, comment="区域(对象存储)")
    path_prefix: Mapped[str | None] = mapped_column(String(255), default=None, nullable=True, comment="统一路径前缀")
    is_secure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否启用TLS(FTPS)")
    implicit_tls: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="FTPS是否隐式TLS(默认显式)")
    scheme: Mapped[str] = mapped_column(String(16), default="https", nullable=False, comment="对象存储访问协议(http/https)")
    encrypt_type: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="FTPS加密类型(0=明文 1=显式TLS可用时 2=要求显式TLS 3=隐式TLS)")
    connection_mode: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="FTP/FTPS传输模式(0=默认 1=主动 2=被动)")
    encoding: Mapped[str] = mapped_column(String(16), default="UTF-8", nullable=False, comment="FTP/FTPS/SFTP编码(utf-8/gbk 等)")
    multipart_part_size: Mapped[int] = mapped_column(Integer, default=50, nullable=False, comment="分片大小(MB，对象存储分片上传)")
    multipart_concurrency: Mapped[int] = mapped_column(Integer, default=6, nullable=False, comment="分片上传并发路数")
    multipart_memory_budget: Mapped[int] = mapped_column(Integer, default=512, nullable=False, comment="分片上传内存预算(MB)")
    advanced_config: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True, comment="SDK高级配置(JSON，按协议解析)")
    public_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="公有访问根地址（对应存储真根，包含桶，不含路径前缀）")
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="状态(0:启用 1:停用)")
    description: Mapped[str | None] = mapped_column(Text, default=None, nullable=True, comment="备注")


class StorageSettingModel(MappedBase):
    """系统唯一默认存储指针；id 固定为 1。"""

    __tablename__ = "storage_setting"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"), {"comment": "默认存储设置"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    default_node_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("task_storage_node.id", ondelete="RESTRICT"), nullable=True)
