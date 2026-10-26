"""默认存储指针与公有附件台账；保留历史传输表及旧业务 URL。

Revision ID: c8a4e710b632
Revises: 68a3f2e39fc6
"""
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "c8a4e710b632"
down_revision = "68a3f2e39fc6"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    if "task_storage_node" not in tables:
        return
    columns = {column["name"] for column in inspector.get_columns("task_storage_node")}
    if "public_base_url" not in columns:
        op.add_column("task_storage_node", sa.Column("public_base_url", sa.String(512), nullable=True, comment="公有访问根地址（对应存储真根，包含桶，不含路径前缀）"))
    if "storage_setting" not in tables:
        op.create_table('storage_setting',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('default_node_id', sa.Integer(), nullable=True),
        sa.CheckConstraint('id = 1', name=op.f('ck_storage_setting_singleton')),
        sa.ForeignKeyConstraint(['default_node_id'], ['task_storage_node.id'], name=op.f('fk_storage_setting_default_node_id_task_storage_node'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_storage_setting')),
        comment='默认存储设置'
        )
    if "storage_file" not in tables:
        op.create_table('storage_file',
        sa.Column('topic', sa.String(length=32), nullable=False, comment='附件分类'),
        sa.Column('admin_id', sa.Integer(), nullable=True, comment='首次上传管理员'),
        sa.Column('user_id', sa.Integer(), nullable=True, comment='首次上传前台用户（独立用户模型待接入）'),
        sa.Column('storage_node_id', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False, comment='包含前缀的存储对象路径'),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('origin_name', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('width', sa.Integer(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('sha1', sa.String(length=40), nullable=False),
        sa.Column('upload_count', sa.Integer(), nullable=False),
        sa.Column('last_upload_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Integer(), nullable=False, comment='0可用 1停用'),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('uuid', sa.String(length=64), nullable=False, comment='UUID全局唯一标识'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, comment='是否已删除(0:未删除 1:已删除)'),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=False, comment='更新时间'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
        sa.Column('created_id', sa.Integer(), nullable=True, comment='创建人ID'),
        sa.Column('updated_id', sa.Integer(), nullable=True, comment='更新人ID'),
        sa.Column('deleted_id', sa.Integer(), nullable=True, comment='删除人ID'),
        sa.CheckConstraint('file_size >= 0 AND width >= 0 AND height >= 0 AND upload_count >= 1', name=op.f('ck_storage_file_nonnegative_metadata')),
        sa.ForeignKeyConstraint(['admin_id'], ['sys_user.id'], name=op.f('fk_storage_file_admin_id_sys_user'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_id'], ['sys_user.id'], name=op.f('fk_storage_file_created_id_sys_user'), onupdate='CASCADE', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['deleted_id'], ['sys_user.id'], name=op.f('fk_storage_file_deleted_id_sys_user'), onupdate='CASCADE', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['storage_node_id'], ['task_storage_node.id'], name=op.f('fk_storage_file_storage_node_id_task_storage_node'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_id'], ['sys_user.id'], name=op.f('fk_storage_file_updated_id_sys_user'), onupdate='CASCADE', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_storage_file')),
        sa.UniqueConstraint('storage_node_id', 'file_path', name='uq_storage_file_path'),
        comment='存储附件表'
        )
        op.create_index(op.f('ix_storage_file_admin_id'), 'storage_file', ['admin_id'], unique=False)
        op.create_index(op.f('ix_storage_file_created_id'), 'storage_file', ['created_id'], unique=False)
        op.create_index(op.f('ix_storage_file_created_time'), 'storage_file', ['created_time'], unique=False)
        op.create_index('ix_storage_file_dedup', 'storage_file', ['storage_node_id', 'admin_id', 'user_id', 'topic', 'sha1', 'file_size'], unique=False)
        op.create_index(op.f('ix_storage_file_deleted_id'), 'storage_file', ['deleted_id'], unique=False)
        op.create_index(op.f('ix_storage_file_id'), 'storage_file', ['id'], unique=False)
        op.create_index(op.f('ix_storage_file_is_deleted'), 'storage_file', ['is_deleted'], unique=False)
        op.create_index(op.f('ix_storage_file_sha1'), 'storage_file', ['sha1'], unique=False)
        op.create_index(op.f('ix_storage_file_storage_node_id'), 'storage_file', ['storage_node_id'], unique=False)
        op.create_index(op.f('ix_storage_file_topic'), 'storage_file', ['topic'], unique=False)
        op.create_index(op.f('ix_storage_file_updated_id'), 'storage_file', ['updated_id'], unique=False)
        op.create_index(op.f('ix_storage_file_user_id'), 'storage_file', ['user_id'], unique=False)
        op.create_index(op.f('ix_storage_file_uuid'), 'storage_file', ['uuid'], unique=True)
    if "storage_file_reference" not in tables:
        op.create_table('storage_file_reference',
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('business_type', sa.String(length=64), nullable=False),
        sa.Column('business_id', sa.String(length=64), nullable=False),
        sa.Column('field', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['storage_file.id'], name=op.f('fk_storage_file_reference_file_id_storage_file'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('file_id', 'business_type', 'business_id', 'field', name=op.f('pk_storage_file_reference')),
        comment='业务附件引用表'
        )
    metadata = sa.MetaData()
    nodes = sa.Table("task_storage_node", metadata, autoload_with=connection)
    setting = sa.Table("storage_setting", metadata, autoload_with=connection)
    # 原默认标记有歧义则留空，由管理员明确设置；不选择任意节点。
    if connection.scalar(sa.select(setting.c.id).where(setting.c.id == 1)) is None:
        default_id = None
        if "is_default" in nodes.c:
            ids = connection.scalars(sa.select(nodes.c.id).where(nodes.c.is_default.is_(True), nodes.c.is_deleted.is_(False), nodes.c.status == 0)).all()
            if len(ids) == 1:
                default_id = ids[0]
        connection.execute(setting.insert().values(id=1, default_node_id=default_id))
    connection.execute(nodes.update().where(nodes.c.protocol == "local", nodes.c.host == "static/upload", nodes.c.public_base_url.is_(None)).values(public_base_url="/static/upload"))
    # 自动迁移已移除旧标记；内置本地目录无歧义时恢复默认指针。
    if connection.scalar(sa.select(setting.c.default_node_id).where(setting.c.id == 1)) is None:
        local_ids = connection.scalars(sa.select(nodes.c.id).where(nodes.c.name == "本地上传目录", nodes.c.protocol == "local", nodes.c.host == "static/upload", nodes.c.status == 0, nodes.c.is_deleted.is_(False))).all()
        if len(local_ids) == 1:
            connection.execute(setting.update().where(setting.c.id == 1).values(default_node_id=local_ids[0]))
    _upgrade_menus(connection)


def _upgrade_menus(connection):
    if "sys_menu" not in sa.inspect(connection).get_table_names():
        return
    metadata = sa.MetaData()
    menus = sa.Table("sys_menu", metadata, autoload_with=connection)
    rows = connection.execute(sa.select(menus)).mappings().all()
    storage = next((row for row in rows if row["route_name"] == "Storage" and not row["is_deleted"]), None)
    if not storage:
        return
    now = datetime.now(UTC)
    obsolete = {row["id"] for row in rows if (row["permission"] or "").startswith(("module_task:storage:flow:", "module_task:storage:transfer:")) or row["component_path"] in ("module_task/storage/workflow/index", "module_task/storage/transfer/index")}
    obsolete.update(row["id"] for row in rows if row["permission"] in ("module_task:storage:browse:delete", "module_task:storage:browse:update", "module_task:storage:browse:upload"))
    while True:
        expanded = obsolete | {row["id"] for row in rows if row["parent_id"] in obsolete}
        if expanded == obsolete:
            break
        obsolete = expanded
    if obsolete:
        connection.execute(menus.update().where(menus.c.id.in_(obsolete)).values(is_deleted=True, deleted_time=now, status=1))
    connection.execute(menus.update().where(menus.c.id == storage["id"]).values(redirect="/storage/file", description="默认存储节点、附件管理与文件浏览"))
    # 新权限由管理员显式分配，不扩大已有角色授权。
    if any(row["route_name"] == "StorageFile" and not row["is_deleted"] for row in rows):
        return
    def insert(**values):
        data = {"uuid": str(uuid4()), "is_deleted": False, "created_time": now, "updated_time": now, "status": 0,
                "hidden": False, "keep_alive": True, "always_show": False, "affix": False, "is_iframe": False,
                "is_hide_tab": False, "show_badge": False, "scope": "web"}
        data.update(values)
        result = connection.execute(menus.insert().values(**data))
        return result.inserted_primary_key[0]
    parent = insert(name="附件管理", title="附件管理", type=2, order=1, permission="module_task:storage:file:query", route_name="StorageFile", route_path="file", component_path="module_task/storage/file/index", parent_id=storage["id"], icon="ri:attachment-line")
    for index, (label, action) in enumerate((("查询", "query"), ("编辑", "update"), ("删除", "delete")), 1):
        insert(name=label, title=label, type=3, order=index, permission="module_task:storage:file:" + action, parent_id=parent)


def downgrade():
    # 不自动销毁附件记录、引用或恢复废弃菜单，回退必须先处理业务数据。
    raise RuntimeError("文件存储迁移包含业务附件数据，不支持自动回退")
