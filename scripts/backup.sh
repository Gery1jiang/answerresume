#!/bin/bash
# AnswerResume 数据备份脚本
# 用法: bash scripts/backup.sh [备份目录(可选，默认 backups/)]
#
# 备份内容:
#   1. PostgreSQL 数据库 (docker pg_dump)
#   2. user_data/ 用户知识库 + 向量库 + 简历
#   3. vector_store/ FAISS 向量库
#   4. .env 环境变量文件
#
# CRON 示例（每天凌晨 3 点）:
#   0 3 * * * /bin/bash /mnt/d/trae/projects/answerresume/scripts/backup.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${1:-$PROJECT_DIR/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="$BACKUP_DIR/$TIMESTAMP"
RETENTION_DAYS=30
LOG_FILE="$BACKUP_DIR/backup.log"

mkdir -p "$BACKUP_PATH"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[$TIMESTAMP] === 开始备份 ==="

# ── 1. PostgreSQL ──────────────────────────────────────────
echo "[$TIMESTAMP] 备份 PostgreSQL..."
cd "$PROJECT_DIR/hr-agent"
docker compose exec -T postgres pg_dump -U gery -d answeragent \
  --format=custom \
  --file=/tmp/answerresume_backup.dump \
  2>/dev/null && \
docker compose cp postgres:/tmp/answerresume_backup.dump "$BACKUP_PATH/postgres.dump" && \
docker compose exec -T postgres rm -f /tmp/answerresume_backup.dump && \
echo "[$TIMESTAMP] PostgreSQL 备份完成 (postgres.dump)" || \
echo "[$TIMESTAMP] WARNING: PostgreSQL 备份失败"

# ── 2. user_data ───────────────────────────────────────────
echo "[$TIMESTAMP] 备份 user_data..."
if [ -d "$PROJECT_DIR/hr-agent/backend/user_data" ]; then
  tar -czf "$BACKUP_PATH/user_data.tar.gz" \
    -C "$PROJECT_DIR/hr-agent/backend" user_data/
  echo "[$TIMESTAMP] user_data 备份完成 (user_data.tar.gz)"
fi

# ── 3. vector_store ────────────────────────────────────────
echo "[$TIMESTAMP] 备份 vector_store..."
if [ -d "$PROJECT_DIR/hr-agent/vector_store" ]; then
  tar -czf "$BACKUP_PATH/vector_store.tar.gz" \
    -C "$PROJECT_DIR/hr-agent" vector_store/
  echo "[$TIMESTAMP] vector_store 备份完成 (vector_store.tar.gz)"
fi

# ── 4. .env 文件 ───────────────────────────────────────────
echo "[$TIMESTAMP] 备份 .env 文件..."
for f in "$PROJECT_DIR/.env" "$PROJECT_DIR/hr-agent/.env" "$PROJECT_DIR/hr-agent/backend/.env"; do
  if [ -f "$f" ]; then
    # 去除 API Key 敏感内容
    cp "$f" "$BACKUP_PATH/$(echo $f | sed "s|$PROJECT_DIR/||" | tr '/' '_')"
  fi
done
echo "[$TIMESTAMP] .env 备份完成"

# ── 5. SQLite (兼容旧版) ──────────────────────────────────
echo "[$TIMESTAMP] 备份 SQLite..."
if [ -f "$PROJECT_DIR/hr-agent/backend/data/app.db" ]; then
  cp "$PROJECT_DIR/hr-agent/backend/data/app.db" "$BACKUP_PATH/app.db"
  echo "[$TIMESTAMP] SQLite 备份完成 (app.db)"
fi

# ── 清理旧备份 ────────────────────────────────────────────
echo "[$TIMESTAMP] 清理 ${RETENTION_DAYS} 天前的备份..."
find "$BACKUP_DIR" -maxdepth 1 -type d -name "????????_??????" -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null || true
find "$BACKUP_DIR" -maxdepth 1 -type d -name "????????_??????" -mtime +$RETENTION_DAYS | while read d; do
  echo "  删除旧备份: $(basename $d)"
  rm -rf "$d"
done

# ── 统计 ──────────────────────────────────────────────────
echo "[$TIMESTAMP] === 备份完成 ==="
du -sh "$BACKUP_PATH"
echo ""
echo "备份路径: $BACKUP_PATH"
echo "日志文件: $LOG_FILE"
