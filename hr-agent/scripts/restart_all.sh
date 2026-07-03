#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== 一键恢复 answerresume 服务 ==="

if ! docker info >/dev/null 2>&1; then
    echo "✗ Docker 未运行，请先启动 Docker daemon"
    exit 1
fi

# --build [service1 service2 ...]
if [[ "${1:-}" == "--build" ]]; then
    shift
    if [ $# -gt 0 ]; then
        echo "[1/4] 重建指定服务: $*"
        docker compose build "$@"
    else
        echo "[1/4] 重建所有服务..."
        docker compose build
    fi
    echo "[2/4] 拉起服务..."
else
    echo "[1/3] 启动服务..."
fi

docker compose up -d --remove-orphans

echo "    等待 postgres 健康..."
for i in $(seq 1 15); do
    if docker compose exec postgres pg_isready -U gery -d answeragent >/dev/null 2>&1; then
        echo "    postgres 就绪 ✓"
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo "✗ postgres 启动超时"
        docker compose ps
        exit 1
    fi
    sleep 2
done

echo "    等待 backend 就绪..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:51666/health >/dev/null 2>&1; then
        echo "    backend 就绪 ✓"
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo "✗ backend 启动超时"
        docker compose logs --tail=20 backend
        exit 1
    fi
    sleep 2
done

echo ""
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "--- 外部依赖 ---"
if curl -sf http://localhost:10087/command >/dev/null 2>&1; then
    echo "Kimi WebBridge 中继 ✓"
elif systemctl is-active --quiet kimi-webbridge 2>/dev/null; then
    echo "Kimi WebBridge 服务已启动，等待中继就绪..."
    sleep 3
    if curl -sf http://localhost:10087/command >/dev/null 2>&1; then
        echo "Kimi WebBridge 中继 ✓"
    else
        echo "⚠ Kimi 中继仍无响应"
    fi
else
    echo "⚠ Kimi 中继未响应"
    echo "  已安装 systemd 服务: sudo systemctl start kimi-webbridge"
    echo "  手动启动: ~/.kimi-webbridge/bin/kimi-webbridge start"
fi

echo ""
echo "=== 全部就绪 ==="
