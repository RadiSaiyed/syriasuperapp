#!/usr/bin/env bash
set -euo pipefail

# Install and enable systemd timers for nightly DB backups of core stacks.
# Requires sudo/root. Adjust BASE_DIR and TIMES as needed.

BASE_DIR=${BASE_DIR:-/opt/superapp}

# App -> HH:MM schedule (server local time)
declare -A TIMES=(
  [payments]="02:05"
  [taxi]="02:10"
  [commerce]="02:15"
  [doctors]="02:20"
  [food]="02:25"
  [bus]="02:30"
  [freight]="02:35"
  [utilities]="02:40"
  [chat]="02:45"
  [jobs]="02:50"
  [stays]="02:55"
  [automarket]="03:00"
)

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)" >&2
  exit 2
fi

if [[ ! -d "$BASE_DIR" ]]; then
  echo "Base dir $BASE_DIR not found. Set BASE_DIR=/path/to/repo root." >&2
  exit 2
fi

echo "[install] Copying unit templates..."
install -D -m 0644 "$BASE_DIR/ops/backups/systemd/superapp-backup@.service" \
  /etc/systemd/system/superapp-backup@.service
install -D -m 0644 "$BASE_DIR/ops/backups/systemd/superapp-backup@.timer" \
  /etc/systemd/system/superapp-backup@.timer

systemctl daemon-reload

echo "[install] Creating instance timers with staggered schedules..."
for app in "${!TIMES[@]}"; do
  time="${TIMES[$app]}"
  dir="/etc/systemd/system/superapp-backup@${app}.timer.d"
  mkdir -p "$dir"
  cat >"$dir/override.conf" <<EOF
[Timer]
OnCalendar=*-*-* ${time}:00
Persistent=true
EOF
  systemctl enable --now "superapp-backup@${app}.timer" || true
  echo "  - ${app}: ${time}"
done

echo "[install] Done. List timers with: systemctl list-timers | grep superapp-backup@"

