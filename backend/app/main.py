import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import redis
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import settings
from .database import get_connection, init_database

CACHE_KEY = "tasks:list"


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


def redis_client() -> redis.Redis:
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def serialize_task(row: dict[str, Any]) -> dict[str, Any]:
    task = dict(row)
    created_at = task.get("created_at")
    if isinstance(created_at, datetime):
        task["created_at"] = created_at.isoformat()
    return task


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    redis_client().ping()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/health")
def health() -> JSONResponse:
    details = {"api": "ok", "database": "ok", "redis": "ok"}
    status_code = status.HTTP_200_OK

    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        details["database"] = f"error: {type(exc).__name__}"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    try:
        redis_client().ping()
    except Exception as exc:
        details["redis"] = f"error: {type(exc).__name__}"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(status_code=status_code, content=details)


@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate) -> dict[str, Any]:
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                INSERT INTO tasks (title)
                VALUES (%s)
                RETURNING id, title, done, created_at
                """,
                (payload.title,),
            ).fetchone()
            conn.commit()

        redis_client().delete(CACHE_KEY)
        return serialize_task(row)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not create task") from exc


@app.get("/tasks")
def list_tasks(response: Response) -> dict[str, Any]:
    cache = redis_client()
    cached_payload = cache.get(CACHE_KEY)

    if cached_payload:
        response.headers["X-Cache"] = "HIT"
        return json.loads(cached_payload)

    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title, done, created_at
                FROM tasks
                ORDER BY id ASC
                """
            ).fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not list tasks") from exc

    payload = {"items": [serialize_task(row) for row in rows], "count": len(rows)}
    cache.setex(CACHE_KEY, settings.redis_ttl_seconds, json.dumps(payload))
    response.headers["X-Cache"] = "MISS"
    return payload
