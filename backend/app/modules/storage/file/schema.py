from pydantic import BaseModel, Field

from app.core.base_schema import BaseQueryParam, BaseSchema, UploadResponseSchema, UserBySchema
from app.core.validator import DateTimeStr


class StorageFileOutSchema(BaseSchema, UserBySchema, UploadResponseSchema):
    topic: str
    admin_id: int | None = None
    user_id: int | None = None
    storage_node_id: int
    storage_name: str | None = None
    protocol: str | None = None
    sha1: str
    upload_count: int
    last_upload_time: DateTimeStr
    status: int
    reference_count: int = 0


class StorageFileQueryParam(BaseQueryParam):
    origin_name: str | None = Field(None, json_schema_extra={"q": "like"})
    topic: str | None = Field(None, json_schema_extra={"q": "eq"})
    storage_node_id: int | None = Field(None, json_schema_extra={"q": "eq"})
    status: int | None = Field(None, ge=0, le=1, json_schema_extra={"q": "eq"})


class StorageFileUpdateSchema(BaseModel):
    status: int = Field(ge=0, le=1)
