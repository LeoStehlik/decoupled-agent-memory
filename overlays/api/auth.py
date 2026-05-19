import asyncio
import logging
import time
from secrets import compare_digest

import httpx
import jwt
from jwt import PyJWK
from fastapi import HTTPException, Request

from config import settings

logger = logging.getLogger(__name__)

_jwks_cache: dict[str, PyJWK] = {}
_jwks_last_fetch: float = 0
_JWKS_TTL_SECONDS = 15 * 60
_JWKS_MIN_REFRESH_SECONDS = 10
_jwks_lock = asyncio.Lock()


def _jwks_is_stale() -> bool:
    return time.monotonic() - _jwks_last_fetch >= _JWKS_TTL_SECONDS


async def _fetch_jwks() -> None:
    global _jwks_last_fetch
    url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
    data = resp.json()
    new_cache: dict[str, PyJWK] = {}
    for key_data in data.get("keys", []):
        kid = key_data.get("kid")
        if kid:
            new_cache[kid] = PyJWK(key_data)
    _jwks_cache.clear()
    _jwks_cache.update(new_cache)
    _jwks_last_fetch = time.monotonic()
    logger.info("Fetched %d JWKS keys from Supabase", len(_jwks_cache))


async def _refresh_jwks_if_needed(force: bool = False) -> None:
    async with _jwks_lock:
        elapsed = time.monotonic() - _jwks_last_fetch
        if not force and elapsed < _JWKS_MIN_REFRESH_SECONDS:
            return
        if not force and not _jwks_is_stale():
            return
        try:
            await _fetch_jwks()
        except Exception:
            logger.exception("JWKS refresh failed; keeping previous cache")


async def prefetch_jwks() -> None:
    try:
        await _fetch_jwks()
    except Exception:
        logger.exception("Initial JWKS fetch failed; will retry on first auth")


_EXPECTED_ISSUER = settings.SUPABASE_URL.rstrip("/") + "/auth/v1"


async def verify_token(token: str) -> str:
    """Verify a Supabase JWT or trusted static bearer and return user_id."""
    if settings.STATIC_BEARER_TOKEN and compare_digest(token, settings.STATIC_BEARER_TOKEN):
        if not settings.LOCAL_USER_ID:
            raise ValueError("STATIC_BEARER_TOKEN configured but LOCAL_USER_ID is empty")
        return settings.LOCAL_USER_ID

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")

    kid = header.get("kid")
    try:
        if kid:
            if _jwks_is_stale():
                await _refresh_jwks_if_needed()
            if kid not in _jwks_cache:
                await _refresh_jwks_if_needed(force=True)
                if kid not in _jwks_cache:
                    raise ValueError("Unknown signing key")
            jwk = _jwks_cache[kid]
            payload = jwt.decode(
                token,
                jwk.key,
                algorithms=["RS256", "ES256"],
                audience="authenticated",
                issuer=_EXPECTED_ISSUER,
                leeway=30,
                options={
                    "require": ["exp", "iat", "sub", "aud", "iss"],
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                },
            )
        elif settings.SUPABASE_JWT_SECRET:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                leeway=30,
                options={"verify_exp": True, "verify_iat": True, "verify_nbf": True},
            )
        else:
            raise ValueError("Token missing kid header")
    except jwt.InvalidTokenError as e:
        logger.debug("JWT verification failed: %s", e)
        raise ValueError("Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Token missing sub claim")
    return user_id


async def get_current_user(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = auth_header.removeprefix("Bearer ").strip()
    try:
        return await verify_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
