from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from datetime import date, timedelta
from types import ModuleType
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.inventory import InventoryTransaction
from app.repositories.inventory import PostgresInventoryRepository


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_postgres_ready(psycopg_module: ModuleType, dsn: str, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with psycopg_module.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return
        except psycopg_module.Error:
            time.sleep(1)
    raise TimeoutError("PostgreSQL container did not become ready in time")


@pytest.mark.integration
def test_postgres_repository_with_real_container() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker is required for integration test")
    psycopg_module = pytest.importorskip("psycopg", reason="psycopg is required for PostgreSQL integration test")

    try:
        daemon_check = subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        pytest.skip("docker daemon check timed out")

    if daemon_check.returncode != 0:
        pytest.skip("docker daemon is not running")

    host_port = _find_free_port()
    container_name = f"sebastian-pg-test-{uuid4().hex[:8]}"

    run_cmd = [
        "docker",
        "run",
        "-d",
        "--rm",
        "--name",
        container_name,
        "-e",
        "POSTGRES_USER=sebastian",
        "-e",
        "POSTGRES_PASSWORD=sebastian",
        "-e",
        "POSTGRES_DB=sebastian_test",
        "-p",
        f"{host_port}:5432",
        "postgres:16-alpine",
    ]

    db_url = f"postgresql+psycopg://sebastian:sebastian@127.0.0.1:{host_port}/sebastian_test"
    psycopg_dsn = f"postgresql://sebastian:sebastian@127.0.0.1:{host_port}/sebastian_test"

    try:
        run_result = subprocess.run(run_cmd, check=False, capture_output=True, text=True)
        if run_result.returncode != 0:
            message = run_result.stderr.strip() or run_result.stdout.strip() or "unknown docker run error"
            pytest.skip(f"docker run unavailable: {message}")
        _wait_until_postgres_ready(psycopg_module, psycopg_dsn)

        env = os.environ.copy()
        env["DATABASE_URL"] = db_url
        subprocess.run(["alembic", "upgrade", "head"], check=True, env=env, capture_output=True, text=True)

        engine = create_engine(db_url)
        with Session(engine) as db:
            repository = PostgresInventoryRepository(db)
            item = repository.create(
                name="Chicken",
                quantity=2,
                unit="kg",
                expire_date=date.today() + timedelta(days=4),
                note="container test",
            )

            updated = repository.adjust(item.id, -0.5, "used half")
            assert updated.quantity == 1.5

            txs = db.scalars(
                select(InventoryTransaction).where(InventoryTransaction.inventory_id == item.id)
            ).all()
            assert len(txs) == 2
            assert {tx.action for tx in txs} == {"IN", "OUT"}
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], check=False, capture_output=True, text=True)
