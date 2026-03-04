"""Cognito JWT 验证中间件 — 从 JWKS 获取公钥，验证 Token 签名和过期时间。"""

import os

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt

_security = HTTPBearer()

# Cognito 配置
_USER_POOL_ID = os.environ.get("USER_POOL_ID", "")
_REGION = os.environ.get("AWS_REGION_NAME", "ap-northeast-1")
_JWKS_URL = f"https://cognito-idp.{_REGION}.amazonaws.com/{_USER_POOL_ID}/.well-known/jwks.json"
_ISSUER = f"https://cognito-idp.{_REGION}.amazonaws.com/{_USER_POOL_ID}"

# 缓存 JWKS 公钥
_jwks_cache: dict | None = None


def _get_jwks() -> dict:
    """获取并缓存 Cognito JWKS 公钥。"""
    global _jwks_cache
    if _jwks_cache is None:
        resp = httpx.get(_JWKS_URL, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


def _get_signing_key(token: str) -> dict:
    """从 JWKS 中找到匹配 token kid 的公钥。"""
    headers = jwt.get_unverified_headers(token)
    kid = headers.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Token 缺少 kid")

    jwks_data = _get_jwks()
    for key in jwks_data.get("keys", []):
        if key["kid"] == kid:
            return key

    raise HTTPException(status_code=401, detail="无法找到匹配的签名密钥")


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    """验证 Cognito JWT Token，返回用户信息字典。

    Returns:
        {"username": str, "sub": str, "claims": dict}
    """
    token = credentials.credentials

    try:
        signing_key = _get_signing_key(token)
        public_key = jwk.construct(signing_key)

        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=_ISSUER,
            options={"verify_aud": False},
        )

        username = claims.get("cognito:username") or claims.get("username", "")
        sub = claims.get("sub", "")

        return {"username": username, "sub": sub, "claims": claims}

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token 验证失败: {str(e)}")
    except Exception:
        raise HTTPException(status_code=401, detail="Token 验证失败")
