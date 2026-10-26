"""为已有可用附件建立规范查重指纹；保留重复历史记录及文件。"""
import hashlib
import json

import sqlalchemy as sa
from alembic import op

revision = "f621b9a0d745"
down_revision = "923815682316"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if "storage_file" not in sa.inspect(connection).get_table_names():
        return
    files = sa.Table("storage_file", sa.MetaData(), autoload_with=connection)
    # 正常历史数据均为空；幂等地保留已经建立的规范记录。
    used = set(connection.scalars(sa.select(files.c.dedup_key).where(files.c.dedup_key.is_not(None))))
    last_id = 0
    while True:
        rows = connection.execute(sa.select(files).where(files.c.id > last_id).order_by(files.c.id).limit(500)).mappings().all()
        if not rows:
            break
        for row in rows:
            if row["dedup_key"] is not None or row["is_deleted"] or row["status"] != 0:
                continue
            values = [row["storage_node_id"], row["admin_id"], row["user_id"], row["topic"], row["sha1"], row["file_size"]]
            key = hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()
            if key not in used:
                connection.execute(files.update().where(files.c.id == row["id"]).values(dedup_key=key))
                used.add(key)
        last_id = rows[-1]["id"]


def downgrade():
    # 数据补全不需要撤销；旧文件 ID 和引用不受影响。
    pass
