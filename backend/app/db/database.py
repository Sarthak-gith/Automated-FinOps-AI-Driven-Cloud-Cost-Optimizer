"""SQLAlchemy engine and reliable local schema initialization."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./backend/data/finops.db")


def make_engine(url: str | None = None):
    selected = url or database_url()
    options = {"check_same_thread": False} if selected.startswith("sqlite") else {}
    if selected.startswith("sqlite:///") and ":memory:" not in selected:
        path = selected.removeprefix("sqlite:///")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(selected, connect_args=options, future=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database(target_engine=None) -> None:
    from app.db import models  # noqa: F401 — register every model before create_all

    Base.metadata.create_all(target_engine or engine)
