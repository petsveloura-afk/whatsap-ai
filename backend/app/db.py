import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
URL = os.environ.get("DATABASE_URL", "sqlite:///./sniper.db")
if URL.startswith("postgres://"): URL = "postgresql://" + URL[11:]
if URL.startswith("postgresql://"): URL = "postgresql+psycopg://" + URL[13:]
engine = create_engine(URL, connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
