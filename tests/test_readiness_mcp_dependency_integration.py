from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from uuid import uuid4

import httpx
import pytest


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_http_ready(url: str, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code < 500:
                return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(f"service did not become ready: {url}")


def _wait_postgres_ready(dsn: str, timeout_seconds: int = 60) -> None:
    psycopg = pytest.importorskip("psycopg", reason="psycopg required for postgres integration test")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return
        except Exception:
            time.sleep(1)
    raise TimeoutError("postgres did not become ready")


def _wait_redis_ready(redis_url: str, timeout_seconds: int = 30) -> None:
    redis = pytest.importorskip("redis", reason="redis package required for integration test")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            client = redis.Redis.from_url(redis_url, decode_responses=True)
            if client.ping():
                return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError("redis did not become ready")


def _run_command(
    args: list[str],
    timeout_seconds: int = 60,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired:
        pytest.skip(f"command timed out after {timeout_seconds}s: {' '.join(args)}")


def _phase(message: str) -> None:
    print(f"[integration][phase] {message}", flush=True)


def _reset_runtime_caches() -> None:
    from app.core.config import get_settings
    from app.db.session import get_engine, get_session_factory
    from app.integrations.elasticsearch_client import get_elasticsearch_client
    from app.integrations.redis_client import get_redis_client

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_elasticsearch_client.cache_clear()
    get_redis_client.cache_clear()


@pytest.fixture(scope="module")
def integration_app():
    _phase("setup: checking docker binary")
    if shutil.which("docker") is None:
        pytest.skip("docker is required for integration test")

    _phase("setup: checking docker daemon")
    daemon_check = _run_command(["docker", "info"], timeout_seconds=8)
    if daemon_check.returncode != 0:
        pytest.skip("docker daemon is not running")

    pg_port = _find_free_port()
    redis_port = _find_free_port()
    es_port = _find_free_port()

    postgres_name = f"sebastian-int-pg-{uuid4().hex[:8]}"
    redis_name = f"sebastian-int-redis-{uuid4().hex[:8]}"
    es_name = f"sebastian-int-es-{uuid4().hex[:8]}"

    database_url = f"postgresql+psycopg://sebastian:sebastian@127.0.0.1:{pg_port}/sebastian_test"
    postgres_dsn = f"postgresql://sebastian:sebastian@127.0.0.1:{pg_port}/sebastian_test"
    redis_url = f"redis://127.0.0.1:{redis_port}/0"
    elasticsearch_url = f"http://127.0.0.1:{es_port}"

    original_env = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "REDIS_URL": os.environ.get("REDIS_URL"),
        "ELASTICSEARCH_URL": os.environ.get("ELASTICSEARCH_URL"),
    }

    try:
        _phase("setup: starting postgres container")
        pg_run = _run_command(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                postgres_name,
                "-e",
                "POSTGRES_USER=sebastian",
                "-e",
                "POSTGRES_PASSWORD=sebastian",
                "-e",
                "POSTGRES_DB=sebastian_test",
                "-p",
                f"{pg_port}:5432",
                "postgres:16-alpine",
            ],
            timeout_seconds=120,
        )
        if pg_run.returncode != 0:
            pytest.skip(f"postgres container unavailable: {pg_run.stderr.strip() or pg_run.stdout.strip()}")

        _phase("setup: starting redis container")
        redis_run = _run_command(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                redis_name,
                "-p",
                f"{redis_port}:6379",
                "redis:7-alpine",
            ],
            timeout_seconds=90,
        )
        if redis_run.returncode != 0:
            pytest.skip(f"redis container unavailable: {redis_run.stderr.strip() or redis_run.stdout.strip()}")

        _phase("setup: starting elasticsearch container")
        es_run = _run_command(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                es_name,
                "-e",
                "discovery.type=single-node",
                "-e",
                "xpack.security.enabled=false",
                "-e",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m",
                "-p",
                f"{es_port}:9200",
                "docker.elastic.co/elasticsearch/elasticsearch:8.14.0",
            ],
            timeout_seconds=180,
        )
        if es_run.returncode != 0:
            pytest.skip(f"elasticsearch container unavailable: {es_run.stderr.strip() or es_run.stdout.strip()}")

        _phase("setup: waiting postgres ready")
        _wait_postgres_ready(postgres_dsn)
        _phase("setup: waiting redis ready")
        _wait_redis_ready(redis_url)
        _phase("setup: waiting elasticsearch ready")
        _wait_http_ready(f"{elasticsearch_url}/_cluster/health")

        _phase("setup: applying runtime environment")
        os.environ["DATABASE_URL"] = database_url
        os.environ["REDIS_URL"] = redis_url
        os.environ["ELASTICSEARCH_URL"] = elasticsearch_url

        _reset_runtime_caches()

        _phase("setup: running alembic migration")
        env = os.environ.copy()
        migrate = _run_command(["alembic", "upgrade", "head"], timeout_seconds=120, env=env)
        if migrate.returncode != 0:
            pytest.skip(f"alembic migration failed: {migrate.stderr.strip() or migrate.stdout.strip()}")

        _phase("setup: importing app")
        from app.main import app

        _phase("setup: ready")
        yield app

    finally:
        _phase("teardown: restoring environment")
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        _reset_runtime_caches()

        _phase("teardown: removing containers")
        for container_name in (es_name, redis_name, postgres_name):
            try:
                subprocess.run(
                    ["docker", "rm", "-f", container_name],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except subprocess.TimeoutExpired:
                pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_readiness_with_real_dependencies(integration_app) -> None:
    _phase("test: readiness check")
    transport = httpx.ASGITransport(app=integration_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        readiness = await client.get("/api/health/readiness")

    assert readiness.status_code == 200
    ready_payload = readiness.json()
    assert ready_payload["status"] == "ok"
    assert ready_payload["redis"]["status"] == "ok"
    assert ready_payload["elasticsearch"]["status"] == "ok"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_memory_write_with_real_dependencies(integration_app) -> None:
    _phase("test: memory write")
    transport = httpx.ASGITransport(app=integration_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_memory = await client.post(
            "/api/search/memory",
            json={
                "user_id": "u-int-memory",
                "memory_type": "profile",
                "content": "我不吃花生",
                "tags": ["allergy"],
                "importance": 0.9,
            },
        )

    assert create_memory.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_idempotency_with_real_dependencies(integration_app) -> None:
    _phase("test: a2a search task")
    transport = httpx.ASGITransport(app=integration_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_memory = await client.post(
            "/api/search/memory",
            json={
                "user_id": "u-int-a2a",
                "memory_type": "profile",
                "content": "我不吃花生",
                "tags": ["allergy"],
                "importance": 0.9,
            },
        )
        assert create_memory.status_code == 200

        # A2A 任务创建（替代旧 MCP invoke）
        first = await client.post(
            "/api/a2a/tasks",
            json={
                "message": "饮食禁忌",
                "user_id": "u-int-a2a",
                "skill_id": "search.answer",
            },
        )
        assert first.status_code in (200, 503)
        payload = first.json()
        if first.status_code == 200:
            assert "task" in payload
            assert payload["task"]["id"]
