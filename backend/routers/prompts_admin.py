from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.prompt_manager import prompt_manager
from routers.deps import require_super_admin
from services.models.user import User

router = APIRouter(prefix="/api/admin/prompts", tags=["prompts"])


class PromptUpdateRequest(BaseModel):
    content: str
    change_log: str = "更新"
    created_by: str = "admin"


class PromptRollbackRequest(BaseModel):
    created_by: str = "admin"


# ── 列表 ────────────────────────────────────────────

@router.get("")
def list_prompts(admin: User = Depends(require_super_admin)):
    """列出所有提示词及其当前版本。"""
    return {"ok": True, "data": prompt_manager.list_all()}


# ── 详情 + 版本历史 ─────────────────────────────────

@router.get("/{key}")
def get_prompt(key: str, admin: User = Depends(require_super_admin)):
    """获取单个提示词的当前内容 + 版本历史。"""
    prompts = prompt_manager.list_all()
    match = [p for p in prompts if p["key"] == key]
    if not match:
        raise HTTPException(status_code=404, detail="提示词不存在")
    history = prompt_manager.get_history(key)
    content = prompt_manager.get(key)
    return {
        "ok": True,
        "data": {
            **match[0],
            "content": content,
            "history": history,
        },
    }


# ── 更新 ────────────────────────────────────────────

@router.put("/{key}")
def update_prompt(key: str, req: PromptUpdateRequest, admin: User = Depends(require_super_admin)):
    """更新提示词内容（旧版本自动存档）。"""
    ok = prompt_manager.update(
        key=key,
        content=req.content,
        change_log=req.change_log,
        created_by=admin.username,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="更新失败")
    return {"ok": True, "message": f"提示词 {key} 已更新"}


# ── 回退 ────────────────────────────────────────────

@router.post("/{key}/rollback/{version}")
def rollback_prompt(key: str, version: int, req: PromptRollbackRequest = None,
                    admin: User = Depends(require_super_admin)):
    """回退提示词到指定历史版本。"""
    ok = prompt_manager.rollback(
        key=key,
        target_version=version,
        created_by=admin.username,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="版本不存在或回退失败")
    return {"ok": True, "message": f"提示词 {key} 已回退到版本 {version}"}
