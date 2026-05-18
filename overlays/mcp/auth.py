import asyncio
import logging
from secrets import compare_digest

import jwt as pyjwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier

from config import settings

logger = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


def _access_token(token: str, payload: dict) -> AccessToken | None:
    sub = payload.get("sub", "")
    if not sub:
        logger.warning("JWT has no sub claim")
        return None

    scopes = []
    scope_str = payload.get("scope", "")
    if isinstance(scope_str, str) and scope_str:
        scopes = scope_str.split()

    logger.info("MCP auth: %s", sub)
    return AccessToken(
        token=token,
        client_id=sub,
        scopes=scopes,
        extra={"claims": payload},
    )


class SupabaseTokenVerifier(TokenVerifier):

    async def verify_token(self, token: str) -> AccessToken | None:
        if settings.STATIC_BEARER_TOKEN and compare_digest(token, settings.STATIC_BEARER_TOKEN):
            if not settings.LOCAL_USER_ID:
                logger.warning("STATIC_BEARER_TOKEN is configured but LOCAL_USER_ID is empty")
                return None
            return _access_token(
                token,
                {
                    "sub": settings.LOCAL_USER_ID,
                    "aud": "authenticated",
                    "role": "authenticated",
                    "scope": "",
                },
            )

        try:
            header = pyjwt.get_unverified_header(token)
        except pyjwt.InvalidTokenError as e:
            logger.debug("JWT header parsing failed: %s", e)
            return None

        kid = header.get("kid")
        try:
            if kid:
                signing_key = await asyncio.to_thread(
                    _get_jwks_client().get_signing_key_from_jwt, token
                )
                payload = pyjwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256", "ES256"],
                    audience="authenticated",
                )
            elif settings.SUPABASE_JWT_SECRET:
                payload = pyjwt.decode(
                    token,
                    settings.SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    audience="authenticated",
                )
            else:
                logger.debug("JWT has no kid and SUPABASE_JWT_SECRET is not configured")
                return None
        except Exception as e:
            logger.debug("JWT verification failed: %s", e)
            return None

        return _access_token(token, payload)
