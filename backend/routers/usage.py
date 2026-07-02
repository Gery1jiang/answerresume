from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from routers.deps import get_current_user, require_super_admin
from services.usage_service import usage_service
from services.models.user import User

router = APIRouter(prefix="/api/usage", tags=["usage"])


class UsageResponse(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_search_calls: int
    total_api_calls: int


class UserUsageItem(BaseModel):
    user_id: str
    username: str = ""
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_search_calls: int
    total_api_calls: int


class AllUsageResponse(BaseModel):
    users: list[UserUsageItem]
    summary: dict


class DailyUsageItem(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    search_calls: int


@router.get("/my", response_model=UsageResponse)
async def get_my_usage(
    period: str = Query("all", regex="^(today|7d|30d|all)$"),
    current_user: User = Depends(get_current_user),
):
    return usage_service.get_user_usage(current_user.id, period)


@router.get("/all", response_model=AllUsageResponse)
async def get_all_users_usage(
    period: str = Query("all", regex="^(today|7d|30d|all)$"),
    current_user: User = Depends(require_super_admin),
):
    return usage_service.get_all_users_usage(period)


@router.get("/my/daily", response_model=list[DailyUsageItem])
async def get_my_daily_usage(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
):
    return usage_service.get_daily_breakdown(current_user.id, days)


@router.get("/all/daily", response_model=list[DailyUsageItem])
async def get_all_daily_usage(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_super_admin),
):
    return usage_service.get_daily_breakdown(days=days)
