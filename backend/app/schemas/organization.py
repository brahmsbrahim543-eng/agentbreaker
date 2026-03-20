from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrgResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    plan: str
    created_at: datetime
