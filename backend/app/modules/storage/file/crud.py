from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import StorageFileModel
from .schema import StorageFileUpdateSchema


class StorageFileCRUD(CRUDBase[StorageFileModel, BaseModel, StorageFileUpdateSchema]):
    def __init__(self, auth: AuthSchema, db: AsyncSession):
        super().__init__(model=StorageFileModel, auth=auth, db=db)
