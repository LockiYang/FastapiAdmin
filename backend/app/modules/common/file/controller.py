from typing import Annotated, Literal

from fastapi import APIRouter, File, Query, Request, Security, UploadFile
from fastapi.responses import JSONResponse

from app.common.response import ResponseSchema, SuccessResponse
from app.config.setting import settings
from app.core.base_schema import AuthSchema, UploadResponseSchema
from app.core.dependencies import AuthPermission
from app.core.exceptions import CustomException
from app.core.router_class import OperationLogRoute

FileRouter = APIRouter(route_class=OperationLogRoute, prefix="/file", tags=["文件管理"])


@FileRouter.post("/upload", summary="上传文件", response_model=ResponseSchema[UploadResponseSchema])
async def upload_controller(
    request: Request,
    file: Annotated[UploadFile, File(description="上传文件")],
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_common:file:upload"]))],
    upload_type: Annotated[
        Literal["file", "avatar", "param", "resource", "attachment"] | None,
        Query(description="上传类型: file=通用文件, avatar=头像, param=参数配置, resource=监控资源"),
    ] = "file",
) -> JSONResponse:
    if not settings.module_enabled("storage"):
        raise CustomException(msg="存储模块未启用")
    from app.modules.storage.file.upload import UploadService
    result = await UploadService(auth, str(request.base_url)).upload(file, upload_type or "file")
    return SuccessResponse(data=result, msg="上传文件成功")
