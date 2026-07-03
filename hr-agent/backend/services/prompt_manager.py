import hashlib
from datetime import datetime
from typing import Optional
from services.database import SessionLocal
from services.models import PromptTemplate, PromptVersion


class PromptManager:
    """提示词管理器：支持版本管理、变更历史、回退、缓存。"""

    def __init__(self):
        self._cache: dict[str, str] = {}
        self._version_cache: dict[str, int] = {}

    # ── 读取 ──────────────────────────────────────────

    def get(self, key: str, default: str = "") -> str:
        """获取指定提示词的当前版本内容。"""
        return self._cache.get(key, default)

    def get_ver(self, key: str) -> int:
        """获取指定提示词的当前版本号。"""
        return self._version_cache.get(key, 0)

    # ── 写入（自动记录版本） ────────────────────────────

    def update(self, key: str, content: str,
               change_log: str = "更新",
               created_by: str = "system",
               description: str = "") -> bool:
        """更新提示词内容，旧版本自动存入历史表。"""
        db = SessionLocal()
        try:
            prompt = db.query(PromptTemplate).filter(
                PromptTemplate.key == key
            ).first()
            if prompt:
                if prompt.content == content:
                    return True  # 无变化
                old_ver = PromptVersion(
                    prompt_key=key,
                    version=prompt.version,
                    content=prompt.content,
                    change_log=change_log,
                    created_by=created_by,
                )
                db.add(old_ver)
                prompt.content = content
                prompt.version = (prompt.version or 1) + 1
                prompt.created_by = created_by
                if description:
                    prompt.description = description
                prompt.updated_at = datetime.utcnow()
            else:
                prompt = PromptTemplate(
                    key=key, content=content,
                    description=description,
                    version=1, created_by=created_by,
                )
                db.add(prompt)
            db.commit()
            self._cache[key] = content
            self._version_cache[key] = prompt.version
            return True
        except Exception as e:
            db.rollback()
            print(f"[prompt_manager] update failed for '{key}': {e}")
            return False
        finally:
            db.close()

    def update_with_hash_check(self, key: str, content: str,
                                change_log: str = "代码部署更新",
                                created_by: str = "system",
                                description: str = "") -> bool:
        """带 hash 对比的更新：仅内容变化时才创建新版本。"""
        current = self._cache.get(key)
        if current is not None and current == content:
            return True  # 内容完全相同，跳过
        return self.update(key, content, change_log, created_by, description)

    # ── 回退 ──────────────────────────────────────────

    def rollback(self, key: str, target_version: int,
                 created_by: str = "admin") -> bool:
        """回退到指定版本。当前内容会被保存为历史后回退。"""
        db = SessionLocal()
        try:
            prompt = db.query(PromptTemplate).filter(
                PromptTemplate.key == key
            ).first()
            if not prompt:
                return False

            history = db.query(PromptVersion).filter(
                PromptVersion.prompt_key == key,
                PromptVersion.version == target_version
            ).first()
            if not history:
                return False

            # 当前版本入历史
            snapshot = PromptVersion(
                prompt_key=key,
                version=prompt.version,
                content=prompt.content,
                change_log=f"回滚到版本 {target_version}",
                created_by=created_by,
            )
            db.add(snapshot)
            # 恢复旧版本
            prompt.content = history.content
            prompt.version = (prompt.version or 1) + 1
            prompt.updated_at = datetime.utcnow()
            db.commit()
            self._cache[key] = history.content
            self._version_cache[key] = prompt.version
            return True
        except Exception as e:
            db.rollback()
            print(f"[prompt_manager] rollback failed for '{key}': {e}")
            return False
        finally:
            db.close()

    # ── 查询 ──────────────────────────────────────────

    def list_all(self) -> list[dict]:
        """列出所有提示词及其当前版本。"""
        db = SessionLocal()
        try:
            prompts = db.query(PromptTemplate).order_by(
                PromptTemplate.key
            ).all()
            return [
                {
                    "key": p.key,
                    "description": p.description or "",
                    "version": p.version,
                    "content_preview": p.content[:200] if p.content else "",
                    "updated_at": p.updated_at.isoformat() if p.updated_at else "",
                    "created_by": p.created_by or "",
                }
                for p in prompts
            ]
        finally:
            db.close()

    def get_history(self, key: str) -> list[dict]:
        """获取指定提示词的版本历史。"""
        db = SessionLocal()
        try:
            versions = db.query(PromptVersion).filter(
                PromptVersion.prompt_key == key
            ).order_by(PromptVersion.version.desc()).all()
            return [
                {
                    "version": v.version,
                    "content_preview": v.content[:500] if v.content else "",
                    "change_log": v.change_log or "",
                    "created_by": v.created_by or "",
                    "created_at": v.created_at.isoformat() if v.created_at else "",
                }
                for v in versions
            ]
        finally:
            db.close()

    def seed_defaults(self, defaults: list[dict]) -> int:
        """初始化默认提示词（仅当 DB 中不存在时写入）。返回写入数量。"""
        count = 0
        for item in defaults:
            key = item.get("key")
            content = item.get("content", "")
            desc = item.get("description", "")
            # 读取最新版本（包含未持久化的 cache）
            cached = self._cache.get(key)
            if cached is not None:
                if cached == content:
                    continue
                # 内容不同 → 记录代码变更
                self.update(key, content,
                            change_log="代码部署更新",
                            created_by="system",
                            description=desc)
                count += 1
            else:
                # DB 中不存在 → 检查 DB
                db = SessionLocal()
                try:
                    exists = db.query(PromptTemplate).filter(
                        PromptTemplate.key == key
                    ).first()
                finally:
                    db.close()

                if exists:
                    self._cache[key] = exists.content
                    self._version_cache[key] = exists.version
                    if exists.content != content:
                        self.update(key, content,
                                    change_log="代码部署更新",
                                    created_by="system",
                                    description=desc)
                        count += 1
                else:
                    # 真正的新提示词
                    self.update(key, content,
                                change_log="初始版本",
                                created_by="system",
                                description=desc)
                    count += 1
        return count

    def get_content_checksum(self, key: str) -> str:
        """获取内容的 hash，用于代码检测。"""
        content = self._cache.get(key, "")
        return hashlib.md5(content.encode()).hexdigest()


# 全局单例
prompt_manager = PromptManager()
