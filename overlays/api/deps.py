import json
from typing import Annotated, AsyncGenerator

import asyncpg
from fastapi import Depends, Request

from auth import get_current_claims
from scoped_db import ScopedDB


def _quote_literal(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


async def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


async def ensure_user(pool: asyncpg.Pool, claims: dict) -> str:
    user_id = claims["sub"]
    email = claims.get("email")
    metadata = claims.get("user_metadata")
    if not email and isinstance(metadata, dict):
        email = metadata.get("email")
    if not email:
        email = f"{user_id}@local.invalid"

    display_name = None
    if isinstance(metadata, dict):
        display_name = metadata.get("display_name") or metadata.get("full_name")

    await pool.execute(
        """
        INSERT INTO users (id, email, display_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (id) DO UPDATE
        SET email = EXCLUDED.email,
            display_name = COALESCE(users.display_name, EXCLUDED.display_name),
            updated_at = now()
        """,
        user_id,
        email,
        display_name,
    )
    return user_id


async def get_user_id(request: Request) -> str:
    """Authenticate, mirror the auth user locally, and return user_id."""
    claims = await get_current_claims(request)
    return await ensure_user(request.app.state.pool, claims)


async def get_scoped_db(
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> AsyncGenerator[ScopedDB, None]:
    """Read-only scoped DB with RLS enforced. For SELECT routes only."""
    claims = await get_current_claims(request)
    user_id = await ensure_user(pool, claims)
    conn = await pool.acquire()
    tr = conn.transaction()
    await tr.start()
    try:
        claims_json = json.dumps({"sub": user_id})
        await conn.execute("SET LOCAL ROLE authenticated")
        await conn.execute(f"SET LOCAL request.jwt.claims = {_quote_literal(claims_json)}")
        yield ScopedDB(pool, conn, user_id)
        await tr.commit()
    except Exception:
        await tr.rollback()
        raise
    finally:
        await pool.release(conn)
