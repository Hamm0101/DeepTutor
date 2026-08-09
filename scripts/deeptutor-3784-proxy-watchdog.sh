#!/bin/bash
# =====================================================================
# deeptutor-3784-proxy-watchdog.sh
# DeepTutor 手机端前端 HTTP 反代守护脚本（防“进程被回收”）
#
# 守护对象：deeptutor-3784-http-proxy.py
#           （监听 3784，转发到 172.16.105.2:3784 的手机端前端）
# 原理：定期检测 3784 端口是否在监听；若进程不存在或端口未监听，
#       立即用 setsid + nohup 脱离当前会话重新拉起（避免终端断开/
#       会话回收/SIGHUP 把代理带走），并把每次重启事件追加到守护日志。
#
# 用法：
#   方式 A：常驻循环（推荐，部署后不用管）
#       nohup bash scripts/deeptutor-3784-proxy-watchdog.sh \
#           >/tmp/deeptutor-3784-watchdog.log 2>&1 &
#       确认在跑：
#       ps aux | grep deeptutor-3784 | grep -v grep
#
#   方式 B：单次检查（配合 crontab，无需常驻进程，最适合“防回收”）
#       crontab -e 加入下面一行（每 1 分钟检查一次）：
#       * * * * * bash /绝对路径/scripts/deeptutor-3784-proxy-watchdog.sh --once >>/tmp/deeptutor-3784-watchdog.log 2>&1
#
# 环境变量（可选，均有默认值，默认落到脚本同目录以兼容只读 /tmp）：
#   DEEPTUTOR_PROXY_LISTEN            代理监听端口，默认 3784
#   DEEPTUTOR_PROXY_CHECK_INTERVAL    循环模式检查间隔秒，默认 30
#   DEEPTUTOR_PROXY_LOG               代理运行日志，默认 $SCRIPT_DIR/deeptutor-3784-proxy.log
#   DEEPTUTOR_WATCHDOG_LOG            守护日志，默认 $SCRIPT_DIR/deeptutor-3784-watchdog.log
#   DEEPTUTOR_WATCHDOG_LOCK           锁文件，默认 $SCRIPT_DIR/deeptutor-3784-watchdog.lock
# =====================================================================

set -u

# ---------- 配置（可用环境变量覆盖） ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROXY_SCRIPT="$SCRIPT_DIR/deeptutor-3784-http-proxy.py"
LISTEN_PORT="${DEEPTUTOR_PROXY_LISTEN:-3784}"
CHECK_INTERVAL="${DEEPTUTOR_PROXY_CHECK_INTERVAL:-30}"
PROXY_LOG="${DEEPTUTOR_PROXY_LOG:-$SCRIPT_DIR/deeptutor-3784-proxy.log}"
WATCHDOG_LOG="${DEEPTUTOR_WATCHDOG_LOG:-$SCRIPT_DIR/deeptutor-3784-watchdog.log}"
LOCK_FILE="${DEEPTUTOR_WATCHDOG_LOCK:-$SCRIPT_DIR/deeptutor-3784-watchdog.lock}"

say() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$WATCHDOG_LOG"; }

# ---------- 互斥锁：防止 crontab 与常驻循环同时拉起（重复拉起） ----------
if [ -f "$LOCK_FILE" ]; then
  lock_pid="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
    exit 0  # 已有守护实例在跑，本次直接退出
  fi
fi
echo "$$" >"$LOCK_FILE"

# ---------- 健康检测：优先看端口，再看进程 ----------
is_running() {
  # 1) 端口是否在监听（Linux 用 ss，macOS 用 lsof，都没有则退回进程检测）
  if command -v ss >/dev/null 2>&1; then
    if ss -tln | grep -q ":${LISTEN_PORT}[[:space:]]"; then
      return 0
    fi
  elif command -v lsof >/dev/null 2>&1; then
    if lsof -iTCP:"$LISTEN_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
  elif command -v netstat >/dev/null 2>&1; then
    if netstat -tln 2>/dev/null | grep -q ":${LISTEN_PORT}[[:space:]]"; then
      return 0
    fi
  fi
  # 2) 进程是否存活（双保险）
  if pgrep -f "deeptutor-3784-http-proxy.py" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

# ---------- 拉起代理 ----------
start_proxy() {
  if [ ! -f "$PROXY_SCRIPT" ]; then
    say "ERROR 代理脚本不存在: $PROXY_SCRIPT，跳过拉起"
    return 1
  fi
  # setsid 脱离会话：SSH 断开 / 终端关闭 / 登录会话回收都不会把代理带走
  if command -v setsid >/dev/null 2>&1; then
    ( setsid nohup python3 "$PROXY_SCRIPT" >>"$PROXY_LOG" 2>&1 & )
  else
    ( nohup python3 "$PROXY_SCRIPT" >>"$PROXY_LOG" 2>&1 & )
  fi
  sleep 2
  if is_running; then
    say "RECOVER 代理已重新拉起（端口 $LISTEN_PORT 正常监听）"
  else
    say "WARN 重新拉起后仍未检测到端口 $LISTEN_PORT，请手动查看 $PROXY_LOG"
  fi
}

# ---------- 主逻辑 ----------
check_once() {
  if is_running; then
    return 0
  fi
  say "DOWN 检测到代理不可用（端口 $LISTEN_PORT 未监听），开始拉起..."
  start_proxy
}

if [ "${1:-}" = "--once" ]; then
  # 单次检查模式：配合 crontab 使用
  check_once
  rm -f "$LOCK_FILE"
  exit 0
fi

# 常驻循环模式
say "watchdog 启动：守护 $PROXY_SCRIPT（端口 $LISTEN_PORT），每 ${CHECK_INTERVAL}s 检查一次"
trap 'rm -f "$LOCK_FILE"; exit 0' INT TERM EXIT
while true; do
  check_once
  sleep "$CHECK_INTERVAL"
done
