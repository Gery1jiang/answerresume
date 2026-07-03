#!/usr/bin/env bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "请用 sudo 运行: sudo bash $0"
    exit 1
fi

COMPOSE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cat > /etc/systemd/system/answerresume-docker.service << EOF
[Unit]
Description=AnswerResume Docker Compose Stack
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=true
ExecStartPre=/bin/sh -c 'for i in \$(seq 1 15); do docker info >/dev/null 2>&1 && exit 0; sleep 2; done; exit 1'
ExecStart=/usr/bin/docker compose -f $COMPOSE_DIR/docker-compose.yml up -d --remove-orphans
ExecStop=/usr/bin/docker compose -f $COMPOSE_DIR/docker-compose.yml down
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable answerresume-docker

echo "✓ Docker Compose 已注册为开机自启服务"
echo "  systemctl start answerresume-docker   # 手动启动"
echo "  journalctl -u answerresume-docker     # 查看启动日志"
