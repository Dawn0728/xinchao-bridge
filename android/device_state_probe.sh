#!/system/bin/sh
# 心潮桥 · Android 设备状态探针（公开版）
# 江衍 & 鱼鱼 写于 2026-09-27
# 每 20 秒采样：前台 App / 屏幕亮灭 / 电量 → 写入 sdcard 供 proot/部署端读取
#
# 用法（Android 上，有 Shizuku / Root shell 权限）：
#   nohup /system/bin/sh device_state_probe.sh </dev/null >/dev/null 2>&1 &
#
# 输出路径可通过环境变量 STATE_OUT 覆盖（默认 /sdcard/Download/Operit/inbox/device_state.json）

OUT=${STATE_OUT:-/sdcard/Download/Operit/inbox/device_state.json}
LOG=${STATE_LOG:-/sdcard/Download/Operit/inbox/device_state_probe.log}
mkdir -p "$(dirname "$OUT")" 2>/dev/null

while true; do
  # 前台 App（不同系统路径可能不同，按需调整）
  APP=$(dumpsys window 2>/dev/null | grep 'mCurrentFocus=' | head -1 | sed 's/.*Window{[^}]* u[0-9]* //; s|/.*||')
  [ -z "$APP" ] && APP="unknown"
  # 屏幕亮灭
  SCR=$(dumpsys deviceidle 2>/dev/null | grep 'mScreenOn=' | head -1 | sed 's/.*mScreenOn=//')
  # 电量
  BAT=$(dumpsys battery 2>/dev/null | grep '^  level:' | awk '{print $2}')
  CHG=$(dumpsys battery 2>/dev/null | grep '^  status:' | awk '{print $2}')
  TS=$(date +%s)
  NOW=$(date '+%Y-%m-%d %H:%M')
  cat > "$OUT" <<EOF
{"ts":$TS,"时间":"$NOW","前台App":"$APP","屏幕亮":$SCR,"电量":$BAT,"充电中":$CHG}
EOF
  echo "[$NOW] app=$APP scr=$SCR bat=$BAT chg=$CHG" >> "$LOG"
  sleep 20
done