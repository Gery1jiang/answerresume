import uuid
import os
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel

import hashlib
import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config import settings
from services.database import get_db
from services.repository.container import RepoContainer
from services.models import User, UserConfig
from routers.deps import get_current_user, require_super_admin

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ── helpers ─────────────────────────────────────────────


def _create_token(user: User) -> str:
    payload = {
        "user_id": user.id,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def _hash_password(password: str) -> str:
    salt = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:16]
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"{salt}${hashed}"


def _check_password(password: str, password_hash: str) -> bool:
    parts = password_hash.split("$", 1)
    if len(parts) != 2:
        return False
    salt, stored = parts
    computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return computed == stored


def _init_user_knowledge_dir(user_id: str):
    """Create per-user knowledge directory and seed empty template files."""
    kb_dir = os.path.join(settings.USER_DATA_DIR, user_id, "knowledge")
    os.makedirs(kb_dir, exist_ok=True)
    templates = {
        "01_个人信息.md": "# 个人信息\n\n姓名：\n电话：\n邮箱：\n求职意向：\n",
        "02_教育背景.md": "# 教育背景\n\n学校：\n专业：\n学历：\n时间：\n",
        "03_工作经历.md": "# 工作经历\n\n## 公司名称 | 职位 | 时间\n\n- 工作内容\n",
        "04_项目经历.md": "# 项目经历\n\n## 项目名称 | 角色\n\n- 项目描述\n",
        "05_专业技能栈.md": "# 专业技能\n\n- 技能一\n- 技能二\n",
        "06_HR高频问答库.md": "# HR 高频问答\n\n",
    }
    for filename, content in templates.items():
        filepath = os.path.join(kb_dir, filename)
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)


# ── schemas ─────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    captcha_token: Optional[str] = ""


class LoginRequest(BaseModel):
    login: str  # username or email
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    username: str


class UserInfoResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[str] = None


class UserListResponse(BaseModel):
    users: list[UserInfoResponse]
    total: int


class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "user"


class UpdateUserRequest(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


# ── endpoints ───────────────────────────────────────────


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if len(req.password) < 6:
        raise HTTPException(400, "密码至少6位")
    repo = RepoContainer(db)
    if repo.user.get_by_login(req.login):
        raise HTTPException(409, "用户名或邮箱已存在")

    is_first = not repo.user.exists()
    user = repo.user.create(
        id=str(uuid.uuid4()),
        username=req.username,
        email=req.email,
        password_hash=_hash_password(req.password),
        role="super_admin" if is_first else "user",
    )

    _init_user_knowledge_dir(user.id)

    return AuthResponse(
        access_token=_create_token(user),
        role=user.role,
        user_id=user.id,
        username=user.username,
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    repo = RepoContainer(db)
    user = repo.user.get_by_login(req.login)
    if not user or not _check_password(req.password, user.password_hash):
        raise HTTPException(401, "用户名/邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(403, "账号已禁用")

    return AuthResponse(
        access_token=_create_token(user),
        role=user.role,
        user_id=user.id,
        username=user.username,
    )


@router.get("/me", response_model=UserInfoResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserInfoResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


# ── super_admin: user management ────────────────────────


@router.get("/users", response_model=UserListResponse)
async def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    repo = RepoContainer(db)
    users = repo.user.list_all()
    return UserListResponse(
        users=[
            UserInfoResponse(
                id=u.id,
                username=u.username,
                email=u.email,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at.isoformat() if u.created_at else None,
            )
            for u in users
        ],
        total=len(users),
    )


@router.post("/users", response_model=UserInfoResponse)
async def create_user(
    req: CreateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    repo = RepoContainer(db)
    if repo.user.get_by_login(req.username):
        raise HTTPException(409, "用户名或邮箱已存在")
    if len(req.password) < 6:
        raise HTTPException(400, "密码至少6位")

    user = repo.user.create(
        id=str(uuid.uuid4()),
        username=req.username,
        email=req.email,
        password_hash=_hash_password(req.password),
        role=req.role,
    )

    _init_user_knowledge_dir(user.id)

    return UserInfoResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.put("/users/{user_id}", response_model=MessageResponse)
async def update_user(
    user_id: str,
    req: UpdateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    repo = RepoContainer(db)
    user = repo.user.get_by_id(user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.role is not None:
        user.role = req.role
    db.commit()
    return {"message": "更新成功"}


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    repo = RepoContainer(db)
    user = repo.user.get_by_id(user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id:
        raise HTTPException(400, "不能删除自己")
    db.delete(user)
    db.commit()
    return {"message": "用户已删除"}
