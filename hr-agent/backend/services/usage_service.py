import json
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func, extract
from services.models.llm_usage import LLMUsage
from services.database import SessionLocal


class UsageService:

    def record(self, user_id: str, event_type: str, model: str = "",
               input_tokens: int = 0, output_tokens: int = 0,
               search_calls: int = 0):
        try:
            db = SessionLocal()
            record = LLMUsage(
                user_id=str(user_id),
                event_type=event_type,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                search_calls=search_calls,
            )
            db.add(record)
            db.commit()
            db.close()
        except Exception as e:
            print(f"[usage_service] record error: {e}")

    def _get_date_range(self, period: str):
        today = date.today()
        if period == "today":
            return today, today + timedelta(days=1)
        elif period == "7d":
            return today - timedelta(days=6), today + timedelta(days=1)
        elif period == "30d":
            return today - timedelta(days=29), today + timedelta(days=1)
        else:
            return None, None

    def get_user_usage(self, user_id: str, period: str = "all"):
        db = SessionLocal()
        try:
            start, end = self._get_date_range(period)
            q = db.query(
                func.coalesce(func.sum(LLMUsage.input_tokens), 0).label("total_input"),
                func.coalesce(func.sum(LLMUsage.output_tokens), 0).label("total_output"),
                func.coalesce(func.sum(LLMUsage.search_calls), 0).label("total_search"),
                func.count(LLMUsage.id).label("total_calls"),
            ).filter(LLMUsage.user_id == str(user_id))
            if start and end:
                q = q.filter(LLMUsage.created_at >= start, LLMUsage.created_at < end)
            row = q.first()
            return {
                "total_input_tokens": row.total_input,
                "total_output_tokens": row.total_output,
                "total_tokens": row.total_input + row.total_output,
                "total_search_calls": row.total_search,
                "total_api_calls": row.total_calls,
            }
        finally:
            db.close()

    def get_all_users_usage(self, period: str = "all"):
        db = SessionLocal()
        try:
            from services.models.user import User
            start, end = self._get_date_range(period)

            # Token usage (all records)
            q = db.query(
                LLMUsage.user_id,
                func.coalesce(func.sum(LLMUsage.input_tokens), 0).label("total_input"),
                func.coalesce(func.sum(LLMUsage.output_tokens), 0).label("total_output"),
            )
            if start and end:
                q = q.filter(LLMUsage.created_at >= start, LLMUsage.created_at < end)
            token_rows = {r.user_id: r for r in q.group_by(LLMUsage.user_id).all()}

            # API call counts (only search_api events)
            q_api = db.query(
                LLMUsage.user_id,
                func.count(LLMUsage.id).label("api_calls"),
            ).filter(LLMUsage.event_type == "search_api")
            if start and end:
                q_api = q_api.filter(LLMUsage.created_at >= start, LLMUsage.created_at < end)
            api_rows = {r.user_id: r.api_calls for r in q_api.group_by(LLMUsage.user_id).all()}

            # All user_ids
            all_ids = set(token_rows.keys()) | set(api_rows.keys())

            # Map user_id -> username
            users_map = {}
            if all_ids:
                user_rows = db.query(User).filter(User.id.in_(list(all_ids))).all()
                users_map = {u.id: u.username for u in user_rows}

            grand_total_input = 0
            grand_total_output = 0
            grand_total_api = 0
            per_user = []
            for uid in sorted(all_ids):
                if uid == "visitor":
                    continue
                tr = token_rows.get(uid)
                input_tokens = tr.total_input if tr else 0
                output_tokens = tr.total_output if tr else 0
                api_calls = api_rows.get(uid, 0)
                grand_total_input += input_tokens
                grand_total_output += output_tokens
                grand_total_api += api_calls
                per_user.append({
                    "user_id": uid,
                    "username": users_map.get(uid, ""),
                    "total_input_tokens": input_tokens,
                    "total_output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "total_search_calls": api_calls,
                    "total_api_calls": api_calls,
                })
            return {
                "users": per_user,
                "summary": {
                    "total_input_tokens": grand_total_input,
                    "total_output_tokens": grand_total_output,
                    "total_tokens": grand_total_input + grand_total_output,
                    "total_search_calls": grand_total_api,
                    "total_user_count": len(per_user),
                },
            }
        finally:
            db.close()

    def get_daily_breakdown(self, user_id: str = None, days: int = 30):
        db = SessionLocal()
        try:
            start = date.today() - timedelta(days=days - 1)
            q = db.query(
                func.date(LLMUsage.created_at).label("day"),
                func.coalesce(func.sum(LLMUsage.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(LLMUsage.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(LLMUsage.search_calls), 0).label("search_calls"),
            )
            if user_id:
                q = q.filter(LLMUsage.user_id == str(user_id))
            rows = q.filter(
                LLMUsage.created_at >= start
            ).group_by(
                func.date(LLMUsage.created_at)
            ).order_by(
                func.date(LLMUsage.created_at)
            ).all()
            return [
                {
                    "date": str(r.day),
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "search_calls": r.search_calls,
                }
                for r in rows
            ]
        finally:
            db.close()


usage_service = UsageService()
