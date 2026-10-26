from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    JobOutSchema,
    JobQueryParam,
    SchedulerJobSchema,
    SchedulerStatusSchema,
)
from .service import JobService

CronJobRouter = APIRouter(route_class=OperationLogRoute, prefix="/cronjob/job", tags=["定时任务管理"])


@CronJobRouter.get("/scheduler/status", summary="获取调度器状态", response_model=ResponseSchema[SchedulerStatusSchema], dependencies=[Security(AuthPermission(["module_task:cronjob:job:query"]))])
async def get_scheduler_status_controller() -> JSONResponse:
    data: SchedulerStatusSchema = JobService.get_scheduler_status()
    return SuccessResponse(data=data, msg="获取调度器状态成功")


@CronJobRouter.get("/scheduler/jobs", summary="获取调度器任务列表", response_model=ResponseSchema[list[SchedulerJobSchema]], dependencies=[Security(AuthPermission(["module_task:cronjob:job:query"]))])
async def get_scheduler_jobs_controller() -> JSONResponse:
    data: list[SchedulerJobSchema] = JobService.get_scheduler_jobs()
    return SuccessResponse(data=data, msg="获取调度器任务列表成功")


@CronJobRouter.post("/scheduler/pause", summary="暂停调度器", response_model=ResponseSchema[None], dependencies=[Security(AuthPermission(["module_task:cronjob:job:scheduler"]))])
async def pause_scheduler_controller() -> JSONResponse:
    JobService.pause_scheduler()
    return SuccessResponse(msg="调度器已暂停")


@CronJobRouter.post("/scheduler/resume", summary="恢复调度器", response_model=ResponseSchema[None], dependencies=[Security(AuthPermission(["module_task:cronjob:job:scheduler"]))])
async def resume_scheduler_controller() -> JSONResponse:
    JobService.resume_scheduler()
    return SuccessResponse(msg="调度器已恢复")


@CronJobRouter.get("/log/list", summary="查询执行日志列表", response_model=ResponseSchema[PageResultSchema[JobOutSchema]])
async def get_job_log_list_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_task:cronjob:job:query"]))],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[JobQueryParam, Query()],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    result_dict: PageResultSchema[JobOutSchema] = await JobService(auth, db).get_job_log_page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result_dict, msg="查询执行日志列表成功")


@CronJobRouter.get("/log/detail/{id}", summary="获取执行日志详情", response_model=ResponseSchema[JobOutSchema])
async def get_job_log_detail_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_task:cronjob:job:detail"]))],
    id: Annotated[int, Path(description="日志ID")],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    result_dict: JobOutSchema = await JobService(auth, db).get_job_log_detail(id=id)
    return SuccessResponse(data=result_dict, msg="获取执行日志详情成功")


@CronJobRouter.delete("/log/delete", summary="删除执行日志", response_model=ResponseSchema[None])
async def delete_job_log_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_task:cronjob:job:delete"]))],
    ids: Annotated[list[int], Body(description="ID列表")],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    await JobService(auth, db).delete_job_log(ids=ids)
    return SuccessResponse(msg="删除执行日志成功")
