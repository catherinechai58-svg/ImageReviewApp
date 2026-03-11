"""认证路由 — 登录（含首次修改密码）和修改密码。"""

import os

import boto3
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.app.auth import verify_token
from backend.shared.errors import AuthenticationError, ValidationError

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_cognito = boto3.client("cognito-idp", region_name=os.environ.get("AWS_REGION_NAME", "ap-northeast-1"))
_USER_POOL_ID = os.environ.get("USER_POOL_ID", "")
_CLIENT_ID = os.environ.get("USER_POOL_CLIENT_ID", "")


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""


class ForceChangePasswordRequest(BaseModel):
    username: str = ""
    new_password: str = ""
    session: str = ""


class ChangePasswordRequest(BaseModel):
    access_token: str = ""
    old_password: str = ""
    new_password: str = ""


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest):
    """POST /auth/login — 登录，首次登录返回 challenge。"""
    if not body.username or not body.password:
        details = []
        if not body.username:
            details.append({"field": "username", "message": "用户名不能为空"})
        if not body.password:
            details.append({"field": "password", "message": "密码不能为空"})
        raise ValidationError("用户名和密码不能为空", details=details)

    try:
        resp = _cognito.admin_initiate_auth(
            UserPoolId=_USER_POOL_ID,
            ClientId=_CLIENT_ID,
            AuthFlow="ADMIN_USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": body.username, "PASSWORD": body.password},
        )
    except _cognito.exceptions.NotAuthorizedException:
        raise AuthenticationError("用户名或密码错误")
    except _cognito.exceptions.UserNotFoundException:
        raise AuthenticationError("用户名或密码错误")
    except Exception:
        raise AuthenticationError("认证失败，请稍后重试")

    # 首次登录需要修改密码
    if resp.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
        return {
            "data": {
                "challenge": "NEW_PASSWORD_REQUIRED",
                "session": resp["Session"],
                "username": body.username,
            },
            "message": "首次登录，请修改密码",
        }

    auth_result = resp.get("AuthenticationResult", {})
    return {
        "data": {
            "id_token": auth_result.get("IdToken"),
            "access_token": auth_result.get("AccessToken"),
            "refresh_token": auth_result.get("RefreshToken"),
            "expires_in": auth_result.get("ExpiresIn"),
            "token_type": auth_result.get("TokenType"),
        },
        "message": "登录成功",
    }


@router.post("/force-change-password")
@limiter.limit("10/minute")
async def force_change_password(request: Request, body: ForceChangePasswordRequest):
    """POST /auth/force-change-password — 首次登录强制修改密码。"""
    if not body.username or not body.new_password or not body.session:
        raise ValidationError("参数不完整")

    try:
        resp = _cognito.admin_respond_to_auth_challenge(
            UserPoolId=_USER_POOL_ID,
            ClientId=_CLIENT_ID,
            ChallengeName="NEW_PASSWORD_REQUIRED",
            ChallengeResponses={
                "USERNAME": body.username,
                "NEW_PASSWORD": body.new_password,
            },
            Session=body.session,
        )
    except _cognito.exceptions.InvalidPasswordException:
        raise ValidationError("新密码不符合密码策略要求（至少8位，包含大小写字母和数字）")
    except _cognito.exceptions.NotAuthorizedException:
        raise AuthenticationError("会话已过期，请重新登录")
    except Exception as e:
        raise AuthenticationError(f"密码修改失败: {str(e)[:200]}")

    auth_result = resp.get("AuthenticationResult", {})
    return {
        "data": {
            "id_token": auth_result.get("IdToken"),
            "access_token": auth_result.get("AccessToken"),
            "refresh_token": auth_result.get("RefreshToken"),
            "expires_in": auth_result.get("ExpiresIn"),
            "token_type": auth_result.get("TokenType"),
        },
        "message": "密码修改成功",
    }


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, user: dict = Depends(verify_token)):
    """POST /auth/change-password — 已登录用户修改密码。"""
    missing = []
    if not body.access_token:
        missing.append({"field": "access_token", "message": "访问令牌不能为空"})
    if not body.old_password:
        missing.append({"field": "old_password", "message": "旧密码不能为空"})
    if not body.new_password:
        missing.append({"field": "new_password", "message": "新密码不能为空"})
    if missing:
        raise ValidationError("请求参数不完整", details=missing)

    try:
        _cognito.change_password(
            PreviousPassword=body.old_password,
            ProposedPassword=body.new_password,
            AccessToken=body.access_token,
        )
    except _cognito.exceptions.NotAuthorizedException:
        raise AuthenticationError("旧密码验证失败")
    except _cognito.exceptions.InvalidPasswordException:
        raise ValidationError("新密码不符合密码策略要求")
    except Exception:
        raise AuthenticationError("密码修改失败，请稍后重试")

    return {"message": "密码修改成功"}
