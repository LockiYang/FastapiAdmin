from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import MappedBase, ModelMixin, UserMixin


class StorageFileModel(ModelMixin, UserMixin):
    """公有附件；路径相对存储真根，包含上传时的 path_prefix。"""

    __tablename__ = "storage_file"
    __table_args__ = (
        UniqueConstraint("storage_node_id", "file_path", name="uq_storage_file_path"),
        CheckConstraint("file_size >= 0 AND width >= 0 AND height >= 0 AND upload_count >= 1", name="nonnegative_metadata"),
        {"comment": "存储附件表"},
    )

    topic: Mapped[str] = mapped_column(String(32), default="file", nullable=False, index=True, comment="附件分类")
    admin_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True, index=True, comment="首次上传管理员")
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True, comment="首次上传前台用户（独立用户模型待接入）")
    storage_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("task_storage_node.id", ondelete="RESTRICT"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, comment="包含前缀的存储对象路径")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    origin_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dedup_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, comment="可用附件的查重指纹，停用或删除后释放")
    sha1: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    upload_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_upload_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="0可用 1停用")


class StorageFileReferenceModel(MappedBase):
    """新业务在自身事务中维护引用；业务数据与引用一同提交/回滚。"""

    __tablename__ = "storage_file_reference"
    __table_args__ = {"comment": "业务附件引用表"}

    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("storage_file.id", ondelete="RESTRICT"), primary_key=True)
    business_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    field: Mapped[str] = mapped_column(String(64), primary_key=True)
