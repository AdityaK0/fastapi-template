from sqlalchemy import create_engine
from config import settings
from sqlalchemy.orm import DeclarativeBase, sessionmaker


engine = create_engine(settings.DATABASE_URL, echo=True)

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