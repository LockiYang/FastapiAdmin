from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Request, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import StorageFileOutSchema, StorageFileQueryParam, StorageFileUpdateSchema
from .service import AttachmentService

StorageAttachmentRouter = APIRouter(route_class=OperationLogRoute, prefix="/storage/file", tags=["附件管理"])


@StorageAttachmentRouter.get("/page", response_model=ResponseSchema[PageResultSchema[StorageFileOutSchema]], summary="附件列表")
async def page_attachments(
    request: Request,
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_task:storage:file:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter, scope="function")],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[StorageFileQueryParam, Query()],
):
    return SuccessResponse(data=await AttachmentService(auth, db, str(request.base_url)).page(search, page.page_no, page.page_size, page.order_by))


@StorageAttachmentRouter.get("/detail/{id}", response_model=ResponseSchema[StorageFileOutSchema], summary="附件详情")
async def detail_attachment(
    request: Request,
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_task:storage:file:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter, scope="function")],
    id: Annotated[int, Path(ge=1)],
):
    return SuccessResponse(data=await AttachmentService(auth, db, str(request.base_url)).detail(id))


@StorageAttachmentRouter.put("/update/{id}", response_model=ResponseSchema[None], summary="附件启停（不改变公有文件访问）")
async def update_attachment(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_task:storage:file:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter, scope="function")],
    id: Annotated[int, Path(ge=1)],
    data: Annotated[StorageFileUpdateSchema, Body()],
):
    await AttachmentService(auth, db).update_status(id, data.status)
    return SuccessResponse(msg="附件状态已更新")


@StorageAttachmentRouter.delete("/delete", response_model=ResponseSchema[None], summary="逻辑删除附件（保留实际文件）")
async def delete_attachments(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_task:storage:file:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter, scope="function")],
    ids: Annotated[list[int], Body()],
):
    await AttachmentService(auth, db).delete(ids)
    return SuccessResponse(msg="附件记录已删除，实际文件保留")
