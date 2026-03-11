"""用户管理路由 — 管理员创建/删除/列表用户，基于 Cognito + DynamoDB Users 表。"""

import os
from datetime import datetime, timezone

import boto3
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.auth import verify_token
from backend.shared import dynamodb
from backend.shared.errors import AuthenticationError, ConflictError, NotFoundError, ValidationError

router = APIRouter()

_cognito = boto3.client("cognito-idp", region_name=os.environ.get("AWS_REGION_NAME", "ap-northeast-1"))
_USER_POOL_ID = os.environ.get("USER_POOL_ID", "")
_USERS_TABLE = os.environ.get("USERS_TABLE", "ImageReviewApp-Users")

ADMIN_ROLE = "admin"
USER_ROLE = "user"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_admin(user: dict) -> None:
    """检查当前用户是否为管理员。"""
    username = user.get("username", "")
    record = dynamodb.get_item(_USERS_TABLE, {"user_id": username})
    if not record or record.get("role") != ADMIN_ROLE:
        raise AuthenticationError("需要管理员权限")


class CreateUserRequest(BaseModel):
    username: str = ""
    temporary_password: str = ""
    role: str = "user"


class ResetPasswordRequest(BaseModel):
    temporary_password: str = ""


# ── /me 必须在 /{username} 之前注册 ──

@router.get("/me")
async def get_current_user(user: dict = Depends(verify_token)):
    """GET /users/me — 获取当前用户信息（含角色）。首个用户自动设为管理员。"""
    username = user.get("username", "")
    record = dynamodb.get_item(_USERS_TABLE, {"user_id": username})

    if not record:
        all_users = dynamodb.scan_all(_USERS_TABLE)
        role = ADMIN_ROLE if not all_users else USER_ROLE
        record = {
            "user_id": username,
            "role": role,
            "created_by": "system",
            "created_at": _now_iso(),
        }
        dynamodb.put_item(_USERS_TABLE, record)

    return {"data": {"username": username, "role": record.get("role", USER_ROLE)}, "message": "查询成功"}


@router.get("")
async def list_users(user: dict = Depends(verify_token)):
    """GET /users — 列出所有用户（管理员）。"""
    _require_admin(user)

    try:
        resp = _cognito.list_users(UserPoolId=_USER_POOL_ID, Limit=60)
    except Exception:
        raise ValidationError("获取用户列表失败")

    db_users = dynamodb.scan_all(_USERS_TABLE)
    role_map = {u["user_id"]: u.get("role", USER_ROLE) for u in db_users}

    result = []
    for u in resp.get("Users", []):
        uname = u["Username"]
        status = u.get("UserStatus", "")
        created = u.get("UserCreateDate")
        result.append({
            "username": uname,
            "status": status,
            "role": role_map.get(uname, USER_ROLE),
            "created_at": created.isoformat() if created else "",
        })
    return {"data": result, "message": "查询成功"}


@router.post("", status_code=201)
async def create_user(body: CreateUserRequest, user: dict = Depends(verify_token)):
    """POST /users — 创建用户（管理员）。"""
    _require_admin(user)

    if not body.username:
        raise ValidationError("用户名不能为空")
    if not body.temporary_password:
        raise ValidationError("临时密码不能为空")
    if body.role not in (ADMIN_ROLE, USER_ROLE):
        raise ValidationError("角色只能为 admin 或 user")

    try:
        _cognito.admin_create_user(
            UserPoolId=_USER_POOL_ID,
            Username=body.username,
            TemporaryPassword=body.temporary_password,
            MessageAction="SUPPRESS",
        )
    except _cognito.exceptions.UsernameExistsException:
        raise ConflictError(f"用户 {body.username} 已存在")
    except _cognito.exceptions.InvalidPasswordException as e:
        raise ValidationError(f"密码不符合策略: {e}")
    except Exception as e:
        raise ValidationError(f"创建用户失败: {str(e)[:200]}")

    dynamodb.put_item(_USERS_TABLE, {
        "user_id": body.username,
        "role": body.role,
        "created_by": user.get("username", ""),
        "created_at": _now_iso(),
    })

    return {"data": {"username": body.username, "role": body.role}, "message": "用户创建成功，首次登录需修改密码"}


@router.put("/{username}/reset-password")
async def reset_password(username: str, body: ResetPasswordRequest, user: dict = Depends(verify_token)):
    """PUT /users/{username}/reset-password — 重置密码（管理员）。"""
    _require_admin(user)

    if not body.temporary_password:
        raise ValidationError("临时密码不能为空")

    try:
        _cognito.admin_set_user_password(
            UserPoolId=_USER_POOL_ID,
            Username=username,
            Password=body.temporary_password,
            Permanent=False,
        )
    except _cognito.exceptions.UserNotFoundException:
        raise NotFoundError(f"用户 {username} 不存在")
    except _cognito.exceptions.InvalidPasswordException as e:
        raise ValidationError(f"密码不符合策略: {e}")
    except Exception as e:
        raise ValidationError(f"重置密码失败: {str(e)[:200]}")

    return {"message": "密码已重置，用户下次登录需修改密码"}


@router.delete("/{username}")
async def delete_user(username: str, user: dict = Depends(verify_token)):
    """DELETE /users/{username} — 删除用户（管理员）。"""
    _require_admin(user)

    current_username = user.get("username", "")
    if username == current_username:
        raise ValidationError("不能删除自己")

    try:
        _cognito.admin_delete_user(UserPoolId=_USER_POOL_ID, Username=username)
    except _cognito.exceptions.UserNotFoundException:
        raise NotFoundError(f"用户 {username} 不存在")
    except Exception as e:
        raise ValidationError(f"删除用户失败: {str(e)[:200]}")

    dynamodb.delete_item(_USERS_TABLE, {"user_id": username})
    return {"message": "用户删除成功"}
