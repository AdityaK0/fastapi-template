from sqlalchemy import create_engine
from config import settings
from sqlalchemy.orm import DeclarativeBase, sessionmaker


connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, connect_args=connect_args)

class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()