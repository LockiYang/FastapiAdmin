import os
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse, UploadFileResponse
from app.core.base_schema import AuthSchema
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute
from app.modules.storage.core.base import StorageObject, StoragePage

from .service import StorageBrowseService

StorageBrowseRouter = APIRouter(route_class=OperationLogRoute, prefix="/storage/browse", tags=["存储管理"])


def _delete_temp_file(path: str) -> None:
    """响应发送后清理临时下载文件。"""
    try:
        os.unlink(path)
    except OSError:
        pass


@StorageBrowseRouter.post("/download", summary="下载存储源文件", response_model=None)
async def download_storage_file_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_task:storage:browse:download"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    background_tasks: BackgroundTasks,
    remote_path: Annotated[str, Body(description="远端文件路径")],
    source_id: Annotated[int | None, Body(description="存储源ID（不传使用默认存储源）")] = None,
    bucket: Annotated[str | None, Body(description="存储桶（对象存储多桶浏览用，可选）")] = None,
) -> UploadFileResponse:
    local_path, file_name = await StorageBrowseService(auth, db).download(
        source_id=source_id, remote_path=remote_path, bucket=bucket
    )
    background_tasks.add_task(_delete_temp_file, local_path)
    return UploadFileResponse(file_path=local_path, filename=file_name)


@StorageBrowseRouter.post("/download_dir", summary="下载存储源目录（递归打包ZIP）", response_model=None)
async def download_dir_storage_file_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_task:storage:browse:download"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    background_tasks: BackgroundTasks,
    remote_path: Annotated[str, Body(description="远端目录路径")],
    source_id: Annotated[int | None, Body(description="存储源ID（不传使用默认存储源）")] = None,
    bucket: Annotated[str | None, Body(description="存储桶（对象存储多桶浏览用，可选）")] = None,
) -> UploadFileResponse:
    local_path, file_name = await StorageBrowseService(auth, db).download_dir(
        source_id=source_id, remote_path=remote_path, bucket=bucket
    )
    background_tasks.add_task(_delete_temp_file, local_path)
    return UploadFileResponse(file_path=local_path, filename=file_name)


@StorageBrowseRouter.get("/list", summary="查询存储源文件列表", response_model=None)
async def list_storage_file_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_task:storage:browse:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    source_id: Annotated[int | None, Query(description="存储源ID（不传使用默认存储源）")] = None,
    prefix: Annotated[str | None, Query(description="目录前缀（可选）")] = None,
    bucket: Annotated[str | None, Query(description="存储桶（对象存储多桶浏览用，可选）")] = None,
    page_size: Annotated[int | None, Query(ge=1, le=500, description="每页数量（传了才走游标分页，不传返回全量）")] = None,
    cursor: Annotated[str | None, Query(description="下一页游标（上一页返回的 next_cursor，可选）")] = None,
) -> JSONResponse:
    result: StoragePage | list[StorageObject] = await StorageBrowseService(auth, db).list_files(
        source_id=source_id, prefix=prefix or "", bucket=bucket, page_size=page_size, cursor=cursor
    )
    return SuccessResponse(data=result, msg="查询文件列表成功")


@StorageBrowseRouter.get("/buckets", summary="查询存储源桶列表", response_model=ResponseSchema[list[str]])
async def list_storage_buckets_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_task:storage:browse:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    source_id: Annotated[int | None, Query(description="存储源ID（不传使用默认存储源）")] = None,
) -> JSONResponse:
    result: list[str] = await StorageBrowseService(auth, db).list_buckets(source_id=source_id)
    return SuccessResponse(data=result, msg="查询桶列表成功")
