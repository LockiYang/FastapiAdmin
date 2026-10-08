"""存储传输模块：

- ``node``: 存储源管理，即“节点”（OSS/COS/OBS/S3/SFTP/FTP 等连接配置）
- ``core``: 对象存储协议适配器与工厂
- ``browse``: 存储文件浏览
- ``transfer``: 传输任务引擎
- ``workflow``: 传输流程编排（画布 CRUD、发布、执行 API）

接口路径为 ``/task/storage``；启停由独立的 ``storage`` 开关控制。
"""
