"""Supabase JWT verification.

Every authenticated request carries `Authorization: Bearer <supabase_access_token>`.

Supabase projects created after the 2024 key-rotation migration sign access
tokens with a per-project asymmetric key (ES256) rather than a shared HS256
secret. We verify against the project's public JWKS endpoint
(`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`) first, matching the token's
`kid`, and fall back to legacy HS256 verification via `SUPABASE_JWT_SECRET`
only if JWKS verification isn't configured or doesn't apply. Either path
extracts `sub` as the user id. Invalid/missing/expired tokens -> 401.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import jwt
import structlog
from fastapi import Header, Request

from app.core.config import get_settings
from app.core.errors import AppError

logger = structlog.get_logger(__name__)

JWT_AUDIENCE = "authenticated"
ASYMMETRIC_ALGORITHMS = ["ES256", "RS256"]
LEGACY_ALGORITHMS = ["HS256"]
# Tolerate small clock skew between this process and Supabase's auth server —
# without it, a freshly issued token can fail the `iat`/`nbf` check purely
# because the two clocks disagree by a couple of seconds.
CLOCK_SKEW_LEEWAY_SECONDS = 10


@lru_cache
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    # PyJWKClient caches fetched keys in-process (lifespan default 300s) so
    # steady-state verification does not hit the network on every request.
    return jwt.PyJWKClient(jwks_url, cache_keys=True)


def _decode(token: str) -> dict:
    settings = get_settings()
    jwks_error: Optional[Exception] = None
    legacy_error: Optional[Exception] = None

    if settings.supabase_jwks_url:
        try:
            client = _jwks_client(settings.supabase_jwks_url)
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=ASYMMETRIC_ALGORITHMS,
                audience=JWT_AUDIENCE,
                leeway=CLOCK_SKEW_LEEWAY_SECONDS,
            )
        except jwt.ExpiredSignatureError as exc:
            raise AppError(code="TOKEN_EXPIRED", message="Access token has expired.", status_code=401) from exc
        except Exception as exc:  # kid not found, network error, wrong alg, etc.
            jwks_error = exc

    if settings.SUPABASE_JWT_SECRET:
        try:
            return jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=LEGACY_ALGORITHMS,
                audience=JWT_AUDIENCE,
                leeway=CLOCK_SKEW_LEEWAY_SECONDS,
            )
        except jwt.ExpiredSignatureError as exc:
            raise AppError(code="TOKEN_EXPIRED", message="Access token has expired.", status_code=401) from exc
        except jwt.PyJWTError as exc:
            legacy_error = exc

    logger.warning(
        "jwt_verification_failed",
        jwks_error=str(jwks_error) if jwks_error else None,
        legacy_error=str(legacy_error) if legacy_error else None,
    )
    raise AppError(code="INVALID_TOKEN", message="Invalid access token.", status_code=401)


async def get_current_user_id(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(
            code="UNAUTHORIZED",
            message="Missing or malformed Authorization header.",
            status_code=401,
        )
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AppError(code="UNAUTHORIZED", message="Missing bearer token.", status_code=401)

    payload = _decode(token)
    user_id = payload.get("sub")
    if not user_id:
        raise AppError(code="INVALID_TOKEN", message="Token is missing the subject claim.", status_code=401)

    # Stash on request.state so downstream dependencies (e.g. rate limiting)
    # can key off the authenticated user rather than falling back to IP.
    request.state.user_id = user_id
    return user_id


async def get_current_user_id_optional(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> Optional[str]:
    """Best-effort variant that never raises — used by dependencies (like rate
    limiting) that must work for both authenticated and anonymous routes."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        payload = _decode(token)
    except AppError:
        return None
    user_id = payload.get("sub")
    if user_id:
        request.state.user_id = user_id
    return user_id
