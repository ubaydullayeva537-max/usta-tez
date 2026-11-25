from app.database import init_db
from app.main import app

init_db()

__all__ = ["app"]
