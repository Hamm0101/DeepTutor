#!/usr/bin/env python3
# =====================================================================
# deeptutor-3784-http-proxy.py
# DeepTutor 手机端前端 HTTP 中转代理（宿主机侧）
#
# 作用：监听 0.0.0.0:3784，把局域网终端的请求原样转发到
#       VM 172.16.105.2:3784 的纯 Web 前端服务（Next/Vite dev）。
#       支持 WebSocket Upgrade / SSE / 长连接，避免 socat 的 Keep-Alive
#       半死连接问题（3783 已验证）。
#
# 用法：
#   直接运行:  python3 deeptutor-3784-http-proxy.py
#   推荐由 deeptutor-3784-proxy-watchdog.sh 守护拉起
#
# 环境变量（可选，均有默认值）：
#   DEEPTUTOR_PROXY_LISTEN        监听端口，默认 3784
#   DEEPTUTOR_PROXY_UPSTREAM_HOST 上游 VM IP，默认 172.16.105.2
#   DEEPTUTOR_PROXY_UPSTREAM_PORT 上游 VM 端口，默认 3784
# =====================================================================

import os
import select
import socket
import sys
import threading
import time

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = int(os.environ.get("DEEPTUTOR_PROXY_LISTEN", "3784"))
UPSTREAM_HOST = os.environ.get("DEEPTUTOR_PROXY_UPSTREAM_HOST", "172.16.105.2")
UPSTREAM_PORT = int(os.environ.get("DEEPTUTOR_PROXY_UPSTREAM_PORT", "3784"))

MAX_HEAD = 2 * 1024 * 1024  # 请求头最大 2MB，防止异常请求撑爆内存
PIPE_TIMEOUT = 60           # select 空闲轮询超时（秒），不关闭连接


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = "[proxy %d->%s:%d] %s %s" % (LISTEN_PORT, UPSTREAM_HOST, UPSTREAM_PORT, ts, msg)
    try:
        print(line, flush=True)
    except Exception:
        pass


def read_request(client):
    """读取完整请求头（含 Content-Length body），返回原始字节。"""
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = client.recv(65536)
        if not chunk:
            return None
        data += chunk
        if len(data) > MAX_HEAD:
            return None
    # 若有 body，按 Content-Length 读满
    try:
        head, _, body_part = data.partition(b"\r\n\r\n")
        cl = 0
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                cl = int(line.split(b":", 1)[1].strip())
                break
        have = len(body_part)
        while have < cl:
            chunk = client.recv(65536)
            if not chunk:
                return None
            data += chunk
            have += len(chunk)
    except Exception:
        pass
    return data


def pipe_both(a, b):
    """双向字节转发，直到任一端关闭。"""
    sockets = [a, b]
    try:
        while True:
            r, _, _ = select.select(sockets, [], [], PIPE_TIMEOUT)
            if not r:
                continue
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                other = b if s is a else a
                try:
                    other.sendall(data)
                except OSError:
                    return
    except (OSError, ValueError):
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


def handle_client(client, addr):
    try:
        client.settimeout(15)
        req = read_request(client)
        if req is None:
            return
        client.settimeout(None)
        up = socket.create_connection((UPSTREAM_HOST, UPSTREAM_PORT), timeout=10)
        try:
            up.sendall(req)
        except OSError:
            return
        pipe_both(client, up)
    except Exception as e:
        log("ERR %s: %s" % (type(e).__name__, e))
    finally:
        try:
            client.close()
        except OSError:
            pass


def main():
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((LISTEN_HOST, LISTEN_PORT))
        srv.listen(256)
    except OSError as e:
        log("FATAL 无法监听 %s:%d: %s" % (LISTEN_HOST, LISTEN_PORT, e))
        sys.exit(1)
    log("listening on %s:%d, upstream %s:%d" % (LISTEN_HOST, LISTEN_PORT, UPSTREAM_HOST, UPSTREAM_PORT))
    while True:
        try:
            conn, addr = srv.accept()
        except OSError:
            time.sleep(0.5)
            continue
        log("client %s:%d connected" % (addr[0], addr[1]))
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()
