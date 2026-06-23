"""conftest — SQLite 文件引擎 + TestClient 共享配置。"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.api.dependencies import get_db_session
from app.db.base import Base
from app.main import app


@pytest.fixture
def engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(f"sqlite+pysqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def client(engine):
    """同步 TestClient，在同一线程内解决 SQLite 连接问题。"""
    app.dependency_overrides[get_db_session] = lambda: Session(engine)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
