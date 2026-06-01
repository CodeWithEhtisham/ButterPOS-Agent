"""Infrastructure smoke tests — Step 0.5."""

import os

import pytest


def test_repo_structure() -> None:
    assert os.path.isdir("docs")
    assert os.path.isfile("docker-compose.yml")
    assert os.path.isfile("requirements.txt")


def test_docker_compose_declares_services() -> None:
    content = open("docker-compose.yml", encoding="utf-8").read()
    assert "postgres:15" in content or "postgres:15-alpine" in content
    assert "redis:7" in content


@pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — run docker compose up first",
)
def test_postgres_connectivity() -> None:
    from scripts.check_infra import check_postgres

    ok, msg = check_postgres()
    assert ok, msg


@pytest.mark.skipif(
    not os.getenv("REDIS_URL"),
    reason="REDIS_URL not set — run docker compose up first",
)
def test_redis_connectivity() -> None:
    from scripts.check_infra import check_redis

    ok, msg = check_redis()
    assert ok, msg
