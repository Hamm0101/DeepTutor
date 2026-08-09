#!/bin/sh
# =====================================================================
# deeptutor-lan-forward.sh
# DeepTutor 局域网访问转发守护脚本
#
# 作用：虚拟机在线时自动拉起 socat 转发（宿主机 3782 -> 虚拟机 3782），
#       虚拟机离线时自动停掉 socat、释放宿主机端口。
# 适用：NAT 网络模式下，让局域网终端通过 宿主机IP:3782 访问虚拟机里的 DeepTutor。
#
# 启动：nohup sh deeptutor-lan-forward.sh >/dev/null 2>&1 &
# 日志：tail -f /tmp/deeptutor-lan-forward.log
# =====================================================================

# ---------- 配置区（按需修改） ----------
LISTEN_PORT=3782          # 宿主机监听端口（局域网终端访问这个端口）
GUEST_IP=172.16.105.2     # openEuler 虚拟机 NAT IP（虚拟机重启后若变了，改这里）
GUEST_PORT=3782           # 虚拟机内 DeepTutor 前端端口
CHECK_INTERVAL=10         # 在线状态探测间隔（秒）
LOG_FILE=/tmp/deeptutor-lan-forward.log
# ---------------------------------------

SOCAT_PID=""

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

# 虚拟机是否在线：优先用 nc 探测 3782 端口，失败则退回 ping
guest_alive() {
  if command -v nc >/dev/null 2>&1; then
    nc -z -w 2 "$GUEST_IP" "$GUEST_PORT" >/dev/null 2>&1 && return 0
  fi
  if command -v ping >/dev/null 2>&1; then
    ping -c 1 -W 2 "$GUEST_IP" >/dev/null 2>&1 && return 0
  fi
  return 1
}

# 虚拟机在线且 socat 未运行时，拉起 socat
ensure_socat() {
  if [ -n "$SOCAT_PID" ] && kill -0 "$SOCAT_PID" 2>/dev/null; then
    return  # 已在运行，什么都不做
  fi
  SOCAT_PID=""
  nohup socat TCP-LISTEN:$LISTEN_PORT,fork,reuseaddr,bind=0.0.0.0 \
    TCP:$GUEST_IP:$GUEST_PORT >> "$LOG_FILE" 2>&1 &
  SOCAT_PID=$!
  log "虚拟机在线，socat 已启动 (PID $SOCAT_PID, $LISTEN_PORT -> $GUEST_IP:$GUEST_PORT)"
}

# 虚拟机离线时，停掉 socat、释放宿主机端口
stop_socat() {
  if [ -n "$SOCAT_PID" ] && kill -0 "$SOCAT_PID" 2>/dev/null; then
    kill "$SOCAT_PID" 2>/dev/null
    log "虚拟机离线，socat 已停止 (PID $SOCAT_PID)"
  fi
  SOCAT_PID=""
}

# 收到中断/退出信号时，把 socat 一并停掉再退出
cleanup() {
  stop_socat
  log "守护脚本退出"
  exit 0
}
trap cleanup INT TERM

log "=== 转发守护脚本启动 (监听 $LISTEN_PORT -> $GUEST_IP:$GUEST_PORT, 每 ${CHECK_INTERVAL}s 探测) ==="

while true; do
  if guest_alive; then
    ensure_socat
  else
    stop_socat
  fi
  sleep "$CHECK_INTERVAL"
done
