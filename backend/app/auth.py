"""Cognito JWT token verification."""

import json
import time
import urllib.request
from functools import lru_cache

from jose import jwt, JWTError
from app.config import settings


@lru_cache(maxsize=1)
def _get_cognito_keys() -> dict:
    """Fetch Cognito JWKS (cached)."""
    url = (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com"
        f"/{settings.cognito_user_pool_id}/.well-known/jwks.json"
    )
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def verify_token(token: str) -> dict | None:
    """Verify a Cognito JWT and return claims, or None if invalid."""
    if not settings.cognito_user_pool_id:
        # Auth disabled in local dev
        return {"sub": "local-dev", "email": "dev@localhost"}

    try:
        keys = _get_cognito_keys()
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        key = None
        for k in keys.get("keys", []):
            if k["kid"] == kid:
                key = k
                break

        if not key:
            return None

        issuer = (
            f"https://cognito-idp.{settings.cognito_region}.amazonaws.com"
            f"/{settings.cognito_user_pool_id}"
        )

        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )

        if claims.get("token_use") not in ("id", "access"):
            return None

        if claims.get("exp", 0) < time.time():
            return None

        return claims

    except JWTError:
        return None
