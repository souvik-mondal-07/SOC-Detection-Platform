from pymongo import ASCENDING, DESCENDING, IndexModel

from app.core.database import COLLECTION_INVESTIGATIONS
from app.models.investigation import Investigation
from app.repositories.base import BaseRepository


class InvestigationRepository(BaseRepository[Investigation]):
    model = Investigation
    collection_name = COLLECTION_INVESTIGATIONS
    id_field = "investigation_id"
    indexes = (
        IndexModel([("investigation_id", ASCENDING)], name="uq_investigation_id", unique=True),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="ix_status_created_at"),  # open investigations
        IndexModel([("created_at", DESCENDING)], name="ix_created_at"),  # newest first
    )
