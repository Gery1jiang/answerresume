#!/usr/bin/env bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "请用 sudo 运行: sudo bash $0"
    exit 1
fi

KIMI_BIN="$(eval echo ~${SUDO_USER:-$USER})/.kimi-webbridge/bin/kimi-webbridge"
ACTUAL_USER="${SUDO_USER:-$USER}"

if [ ! -f "$KIMI_BIN" ]; then
    echo "✗ 未找到 Kimi WebBridge 可执行文件: $KIMI_BIN"
    exit 1
fi

cat > /etc/systemd/system/kimi-webbridge.service << EOF
[Unit]
Description=Kimi WebBridge Daemon
Documentation=https://kimi.com/features/webbridge
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
ExecStart=$KIMI_BIN start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable kimi-webbridge
systemctl start kimi-webbridge

echo "✓ Kimi WebBridge 已注册为系统服务"
echo "  systemctl status kimi-webbridge  # 查看状态"
echo "  systemctl start/stop/restart kimi-webbridge"
