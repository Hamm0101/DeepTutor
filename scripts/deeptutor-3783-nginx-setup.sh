#!/bin/bash
# =====================================================================
# deeptutor-3783-nginx-setup.sh
# DeepTutor 研发前端反代部署脚本（跳板机 = macOS 宿主机）
#
# 作用：为研发前端（VM 172.16.105.2:3783，Next dev）建立 nginx 反代，
#       监听跳板机 3788，供局域网终端 B 访问 http://192.168.51.34:3788。
#       解决 socat 透明转发导致的半死连接问题（Keep-Alive 空闲关闭）。
#
# 用法：在跳板机上执行
#       bash deeptutor-3783-nginx-setup.sh
#       可选参数：GUEST_IP（默认 172.16.105.2）
#
# 前置：macOS + Homebrew（未装 nginx 时脚本会自动 brew install nginx）
# =====================================================================

set -euo pipefail

GUEST_IP="${1:-172.16.105.2}"
GUEST_PORT=3783
LISTEN_PORT=3788
SERVERS_CONF="deeptutor-3783.conf"

say()  { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# ---------- 0. 前置检查 ----------
say "== 0. 前置检查 =="
[ "$(uname -s)" = "Darwin" ] || warn "当前系统不是 macOS，脚本按 macOS 设计，请谨慎使用"
command -v brew >/dev/null 2>&1 || die "未找到 brew，请先安装 Homebrew: https://brew.sh"
command -v nc >/dev/null 2>&1 || warn "未找到 nc，将跳过 VM 连通性探测"
command -v curl >/dev/null 2>&1 || warn "未找到 curl，自动验证步骤将不可用"

# ---------- 1. 确认 nginx（未装则安装） ----------
say "== 1. 确认 nginx =="
if command -v nginx >/dev/null 2>&1; then
  nginx -v 2>&1 | sed 's/^/    /'
else
  say "nginx 未安装，执行: brew install nginx"
  brew install nginx
fi

NGINX_PREFIX="$(brew --prefix nginx 2>/dev/null || true)"
if [ -z "$NGINX_PREFIX" ] || [ ! -d "$NGINX_PREFIX/etc/nginx" ]; then
  die "无法定位 nginx 配置目录（brew --prefix nginx 无效）"
fi
NGINX_ETC="$NGINX_PREFIX/etc/nginx"
NGINX_BIN="$NGINX_PREFIX/bin/nginx"
say "nginx 配置目录: $NGINX_ETC"

# ---------- 2. 连通性探测（VM 3783） ----------
say "== 2. 探测 VM $GUEST_IP:$GUEST_PORT =="
if command -v nc >/dev/null 2>&1; then
  if nc -z -w 3 "$GUEST_IP" "$GUEST_PORT" >/dev/null 2>&1; then
    say "VM $GUEST_IP:$GUEST_PORT 可达 ✓"
  else
    warn "VM $GUEST_IP:$GUEST_PORT 不可达！请确认：1) VM 内 next dev 已启动；2) VM 的 NAT IP 仍为 $GUEST_IP（变了就改脚本首行参数）"
  fi
else
  warn "跳过连通性探测（无 nc）"
fi

# ---------- 3. 检查 3788 端口占用 ----------
say "== 3. 检查端口 $LISTEN_PORT =="
if lsof -iTCP:"$LISTEN_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  die "端口 $LISTEN_PORT 已被占用：$(lsof -iTCP:$LISTEN_PORT -sTCP:LISTEN | tail -1)"
fi
say "端口 $LISTEN_PORT 空闲 ✓"

# ---------- 4. 写入 nginx 配置 ----------
say "== 4. 写入配置 $NGINX_ETC/servers/$SERVERS_CONF =="
mkdir -p "$NGINX_ETC/servers"

cat > "$NGINX_ETC/servers/$SERVERS_CONF" <<EOF
# DeepTutor 研发前端反代：跳板机 ${LISTEN_PORT} -> VM ${GUEST_IP}:${GUEST_PORT}
# 注意：本文件被主配置在 http{} 块内 include，因此文件顶层的 map 合法。
# 若你的主配置没有 include servers/*，请手动把本文件 include 进 http 块。
map \$http_upgrade \$connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen ${LISTEN_PORT};
    server_name _;

    location / {
        proxy_pass http://${GUEST_IP}:${GUEST_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

# 检查主配置是否 include servers 目录
if ! grep -q "servers" "$NGINX_ETC/nginx.conf"; then
  warn "主配置 $NGINX_ETC/nginx.conf 未 include servers 目录，请把 servers/$SERVERS_CONF 手动加入 http 块"
fi

# ---------- 5. 语法检查并加载 ----------
say "== 5. nginx -t && reload =="
"$NGINX_BIN" -t
"$NGINX_BIN" -s reload 2>/dev/null || brew services restart nginx
say "nginx 已 reload"

# ---------- 6. 自动验证 ----------
say "== 6. 验证 =="
sleep 1
if command -v curl >/dev/null 2>&1; then
  code="$(curl -s -m 8 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${LISTEN_PORT}/" || true)"
  say "本机访问 http://127.0.0.1:${LISTEN_PORT}/ -> HTTP $code（200/301/302 均说明链路通）"
  say "后端链路验证: curl -s http://127.0.0.1:${LISTEN_PORT}/api/v1/sessions"
else
  say "无 curl，请手动验证: curl -v http://127.0.0.1:${LISTEN_PORT}/api/v1/sessions"
fi

say ""
say "完成！终端 B 访问: http://192.168.51.34:${LISTEN_PORT}"
say "WebSocket/HMR: /_next/webpack-hmr 应返回 101 Switching Protocols"
say "日志: tail -f $NGINX_ETC/../logs/error.log （brew nginx 日志在 $NGINX_PREFIX/var/log/nginx/error.log）"
