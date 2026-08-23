"""Create all tables in the PostgreSQL database (dev bootstrap; Alembic later if needed)."""
import logging

from app.db.session import engine
from app.models import Base

logger = logging.getLogger(__name__)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("database initialized", extra={"event_data": {"tables": len(Base.metadata.tables)}})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
