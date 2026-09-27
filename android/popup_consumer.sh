#!/system/bin/sh
# 心潮桥 · 弹窗消费者（可选，公开版）
# 江衍 & 鱼鱼 写于 2026-09-27
# 读 inbox/popup_req.json → 发 Android 系统通知
#
# v0.2 主线默认不启用；仅在 bridge_config.json 里"自动弹窗.开启=true"时才写这个文件。
# 想恢复老行为（收到就弹）时，把它起起来即可。
#
# 用法：
#   nohup /system/bin/sh popup_consumer.sh </dev/null >/dev/null 2>&1 &

BASE=${POPUP_BASE:-/sdcard/Download/Operit}
REQ="$BASE/inbox/popup_req.json"
DONE_DIR="$BASE/inbox/_done"
LOG="$BASE/inbox/popup_consumer.log"
mkdir -p "$DONE_DIR" 2>/dev/null

while true; do
  if [ -f "$REQ" ]; then
    RAW=$(cat "$REQ" 2>/dev/null)
    TITLE=$(echo "$RAW" | sed -n 's/.*"title": *"\([^"]*\)".*/\1/p' | head -1)
    TEXT=$(echo "$RAW" | sed -n 's/.*"text": *"\([^"]*\)".*/\1/p' | head -1)
    TS=$(echo "$RAW" | sed -n 's/.*"ts": *"\([0-9]*\).*/\1/p' | head -1)
    TAG="xinchao_${TS:-$(date +%s)}"
    OUT=$(cmd notification post -t "${TITLE:-AI}" "$TAG" "${TEXT:-}" 2>&1)
    RC=$?
    echo "[$(date +%H:%M:%S)] posted rc=$RC tag=$TAG title=$TITLE text=${TEXT:0:60}" >> "$LOG"
    echo "[$(date +%H:%M:%S)] cmd_out=$OUT" >> "$LOG"
    mv "$REQ" "$DONE_DIR/popup_${TS:-now}.json" 2>/dev/null
  fi
  sleep 2
done