#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LanShare - 局域网文件共享工具
================================
功能：
  1. 自选共享文件夹（可多个）
  2. 共享服务独立开关（管理面板常驻，共享服务可随时启停）
  3. 三级权限控制：只读 / 可读写 / 完全控制
  4. 访问密码保护、管理密码保护
  5. 断点续传上传下载、实时访问日志、防火墙一键配置
  6. Web 管理面板，手机电脑均可管理

用法：
  python LanShare.py            # 正常启动（自动打开管理面板）
  python LanShare.py --no-browser   # 不自动打开浏览器
"""

import os
import sys
import json
import time
import shutil
import socket
import hashlib
import mimetypes
import threading
import subprocess
import webbrowser
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import templates

# 让 Windows 控制台正常显示中文
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# PyInstaller 打包后 __file__ 指向临时解压目录，需改用 exe 所在目录
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
RULE_PREFIX = "LanShare_"

DEFAULT_CONFIG = {
    "port": 8766,          # 共享服务端口
    "admin_port": 8765,    # 管理面板端口
    "title": "我的共享",
    "permission": "read",  # read / write / full
    "password": "",        # 访问密码（空=免密）
    "admin_password": "",  # 管理密码（空=仅本机可管理）
    "shares": [],          # [{"name":"下载","path":"C:\\..."}]
    "autostart_share": True,
    "max_upload_mb": 0,    # 0=不限
}

PERM_LEVEL = {"read": 1, "write": 2, "full": 3}


# ============================================================
# 配置
# ============================================================
def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[警告] 配置文件读取失败，使用默认配置：{e}")
    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


CFG = load_config()


# ============================================================
# 日志（内存，最多 500 条）
# ============================================================
LOGS = []
LOG_LOCK = threading.Lock()


def add_log(ip, method, path, status="", size=""):
    with LOG_LOCK:
        LOGS.insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"),
            "ip": ip, "method": method,
            "path": path, "status": str(status), "size": str(size),
        })
        del LOGS[500:]


# ============================================================
# 网络工具
# ============================================================
def get_lan_ips():
    """获取所有局域网 IPv4 地址（跨平台：Windows / Linux / Android-Termux）"""
    import re
    ips = []

    # 1) 主网卡 IP：UDP 连接技术（跨平台最可靠，不依赖外部命令）
    for host in ("223.5.5.5", "8.8.8.8", "192.168.1.1"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((host, 80))
            main_ip = s.getsockname()[0]
            s.close()
            if main_ip and not main_ip.startswith(("127.", "0.")):
                if main_ip not in ips:
                    ips.append(main_ip)
                break
        except Exception:
            continue

    # 2) 枚举全部网卡：Windows 用 ipconfig，Linux 系用 ip addr / ifconfig
    cmds = (["ipconfig"] if os.name == "nt"
            else [["ip", "-4", "addr", "show"], ["ifconfig"]])
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               errors="ignore", timeout=5)
        except Exception:
            continue
        if r.returncode != 0:
            continue
        out = r.stdout or ""
        if os.name == "nt":
            pat = re.finditer(r"(\d+\.\d+\.\d+\.\d+)", out)
        else:
            pat = re.finditer(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
        for m in pat:
            ip = m.group(1)
            if ip.startswith(("127.", "169.254.", "0.", "255.")):
                continue
            if ip not in ips:
                ips.append(ip)
        break  # 用第一个成功的命令即可
    return ips or ["127.0.0.1"]


# ============================================================
# 防火墙
# ============================================================
def firewall(action, ports):
    """action: add / del（仅 Windows；其他平台由系统防火墙自动处理）"""
    if os.name != "nt":
        return "无需操作：当前系统非 Windows，不适用 netsh 防火墙规则"
    msgs = []
    for p in ports:
        name = f"{RULE_PREFIX}{p}"
        cmd = ["netsh", "advfirewall", "firewall",
               "add" if action == "add" else "delete",
               "rule", f"name={name}"]
        if action == "add":
            cmd += ["dir=in", "action=allow", "protocol=TCP", f"localport={p}"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="gbk", errors="ignore")
            ok = (r.returncode == 0)
            msgs.append(f"端口 {p}: {'成功' if ok else '失败'}")
        except Exception as e:
            msgs.append(f"端口 {p}: 异常 {e}")
    return ("已放行 " if action == "add" else "已关闭 ") + "；".join(msgs)


def set_autostart(enable=True):
    """开机自启：Windows 在启动文件夹放 vbs；Linux 系写入 crontab @reboot"""
    if os.name == "nt":
        startup = os.path.join(os.environ.get("APPDATA", ""),
                               r"Microsoft\Windows\Start Menu\Programs\Startup")
        if not os.path.isdir(startup):
            return False, "找不到启动文件夹"
        vbs = os.path.join(startup, "LanShare.vbs")
        try:
            if enable:
                py = sys.executable.replace("python.exe", "pythonw.exe")
                if not os.path.isfile(py):
                    py = sys.executable
                script = os.path.join(APP_DIR, "LanShare.py")
                with open(vbs, "w", encoding="utf-8") as f:
                    f.write(f'Set ws = CreateObject("Wscript.Shell")\n'
                            f'ws.Run """{py}"" ""{script}"" --no-browser", 0, False\n')
                return True, f"已设置开机自启：{vbs}"
            else:
                if os.path.isfile(vbs):
                    os.remove(vbs)
                return True, "已取消开机自启"
        except Exception as e:
            return False, str(e)
    else:
        # Linux / Android：尝试 crontab @reboot
        try:
            script = os.path.abspath(sys.argv[0])
            line = f"@reboot {sys.executable} {script} --no-browser"
            cur = subprocess.run(["crontab", "-l"], capture_output=True,
                                 text=True).stdout or ""
            if enable:
                if line not in cur:
                    new = (cur.rstrip() + "\n" + line + "\n")
                    subprocess.run(["crontab", "-"], input=new, text=True)
                return True, "已设置开机自启（crontab @reboot）"
            else:
                cur = cur.replace(line + "\n", "")
                subprocess.run(["crontab", "-"], input=cur, text=True)
                return True, "已取消开机自启"
        except Exception as e:
            return False, f"开机自启设置失败：{e}"


# ============================================================
# 虚拟路径解析
# ============================================================
def resolve_path(vpath):
    """虚拟路径 -> 真实路径；越界返回 None"""
    vpath = (vpath or "").strip("/")
    parts = [p for p in vpath.split("/") if p and p != ".."]
    shares = CFG.get("shares", [])

    if len(shares) == 1:
        base = shares[0]["path"]
        # 单个共享对象为“文件”时：根或文件名均指向该文件本身
        if os.path.isfile(base):
            return os.path.normpath(base) if len(parts) <= 1 else None
        return os.path.normpath(os.path.join(base, *parts))

    if not parts:
        return None  # 虚拟根目录

    alias = parts[0]
    for sh in shares:
        if sh["name"] == alias:
            sp = sh["path"]
            if os.path.isfile(sp):      # 文件级共享（别名即文件名）
                return os.path.normpath(sp) if len(parts) <= 1 else None
            return os.path.normpath(os.path.join(sp, *parts[1:]))
    return None


def is_allowed(real):
    """检查真实路径是否在共享范围内"""
    if not real:
        return False
    real = os.path.normpath(real)
    for sh in CFG.get("shares", []):
        sp = os.path.normpath(sh["path"])
        if real == sp or real.startswith(sp + os.sep):
            return True
    return False


def human_size(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {u}" if u != "B" else f"{int(n)} B"
        n /= 1024.0
    return f"{n:.1f} PB"


# ============================================================
# 认证
# ============================================================
def expected_token(password):
    return hashlib.md5(("LanShare::" + str(password)).encode()).hexdigest()


def parse_cookies(header):
    d = {}
    for kv in (header or "").split(";"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def gen_qr(url):
    try:
        import qrcode
        import qrcode.image.svg
        img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage)
        import io
        buf = io.BytesIO()
        img.save(buf)
        return buf.getvalue().decode("utf-8")
    except Exception:
        return ""


# ============================================================
# 共享服务 Handler
# ============================================================
class ShareHandler(BaseHTTPRequestHandler):
    server_version = "LanShare/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # 用自定义日志

    # ---------- 工具 ----------
    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False),
                   "application/json; charset=utf-8")

    def _need_auth(self):
        pwd = CFG.get("password", "")
        if not pwd:
            return True
        ck = parse_cookies(self.headers.get("Cookie"))
        return ck.get("ls_sid") == expected_token(pwd)

    def _has(self, level):
        return PERM_LEVEL.get(CFG.get("permission", "read"), 1) >= PERM_LEVEL[level]

    # ---------- 路由 ----------
    def do_GET(self):
        self._route("GET")

    def do_HEAD(self):
        self._route("HEAD")

    def do_PUT(self):
        self._route("PUT")

    def do_POST(self):
        self._route("POST")

    def do_DELETE(self):
        self._route("DELETE")

    def _route(self, method):
        ip = self.client_address[0]
        u = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(u.path)
        qs = urllib.parse.parse_qs(u.query)

        try:
            # 登录
            if path == "/__login" and method == "GET":
                self._login_page(qs.get("next", ["/"])[0], "")
                return
            if path == "/__login" and method == "POST":
                self._do_login(qs)
                return

            if not self._need_auth():
                self._login_page(path, "")
                return

            # API
            if path == "/api/list":
                self._api_list(qs.get("path", [""])[0]); return
            if path.startswith("/raw/"):
                self._download(path[5:], method); return
            if path == "/api/upload" and method == "PUT":
                self._upload(qs.get("path", [""])[0]); return
            if path == "/api/delete" and method == "DELETE":
                self._delete(qs.get("path", [""])[0]); return
            if path == "/api/rename" and method == "POST":
                self._rename(); return
            if path == "/api/mkdir" and method == "POST":
                self._mkdir(); return

            # 客户端页面
            self._send(200, templates.CLIENT_HTML.replace("__TITLE__", CFG.get("title", "共享")),
                       "text/html; charset=utf-8")
        except Exception as e:
            add_log(ip, method, path, "ERR", str(e))
            try:
                self._send(500, f"服务器错误: {e}")
            except Exception:
                pass

    # ---------- 登录 ----------
    def _login_page(self, nxt, err):
        html = templates.LOGIN_HTML.replace("__NEXT__", nxt)
        html = html.replace("__ERR__",
                            f'<div class="hint">{err}</div>' if err else "")
        self._send(401, html, "text/html; charset=utf-8")

    def _do_login(self, qs):
        ln = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(ln).decode("utf-8", "ignore") if ln else ""
        data = urllib.parse.parse_qs(body)
        pwd = data.get("password", [""])[0]
        nxt = data.get("next", ["/"])[0]
        if pwd == CFG.get("password", ""):
            self.send_response(302)
            self.send_header("Location", nxt or "/")
            self.send_header("Set-Cookie",
                             f"ls_sid={expected_token(pwd)}; Path=/; Max-Age=86400")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._login_page(nxt, "密码错误")

    # ---------- 目录列表 ----------
    def _api_list(self, vpath):
        ip = self.client_address[0]
        real = resolve_path(vpath)

        # 虚拟根（多共享时）
        if real is None:
            items = [{"name": s["name"], "is_dir": True, "size": 0, "mtime": ""}
                     for s in CFG.get("shares", [])]
            self._json({"path": "", "permission": CFG.get("permission"),
                        "items": items})
            return

        if os.path.isfile(real):
            # 单文件共享：虚拟根/文件名都指向该文件，直接作为条目返回
            try:
                st = os.stat(real)
                size = st.st_size
            except Exception:
                size = 0
            self._json({
                "path": os.path.basename(real),
                "permission": CFG.get("permission"),
                "single_file": True,
                "items": [{"name": os.path.basename(real), "is_dir": False,
                           "size": size, "mtime": ""}],
            })
            return

        if not os.path.isdir(real):
            self._json({"error": "不是目录"}, 404)
            return

        items = []
        try:
            names = sorted(os.listdir(real),
                           key=lambda x: (not os.path.isdir(os.path.join(real, x)),
                                          x.lower()))
        except Exception as e:
            self._json({"error": str(e)}, 403)
            return

        for n in names:
            full = os.path.join(real, n)
            try:
                st = os.stat(full)
                items.append({
                    "name": n,
                    "is_dir": os.path.isdir(full),
                    "size": 0 if os.path.isdir(full) else st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
            except Exception:
                continue

        add_log(ip, "LIST", vpath or "/", 200, f"{len(items)} 项")
        self._json({"path": vpath, "permission": CFG.get("permission"), "items": items})

    # ---------- 下载（支持续传） ----------
    def _download(self, vpath, method):
        ip = self.client_address[0]
        real = resolve_path(vpath)
        if not real or not is_allowed(real) or not os.path.isfile(real):
            add_log(ip, "GET", vpath, 404)
            self._send(404, "文件不存在")
            return

        size = os.path.getsize(real)
        ctype = mimetypes.guess_type(real)[0] or "application/octet-stream"
        fname = os.path.basename(real)
        start, end = 0, size - 1
        code = 200
        extra = {
            "Accept-Ranges": "bytes",
            "Content-Disposition":
                f'attachment; filename="{fname.encode("ascii","ignore").decode() or "f"}"; '
                f'filename*=UTF-8\'\'{urllib.parse.quote(fname)}',
        }

        rng = self.headers.get("Range")
        if rng:
            import re
            m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
            if m:
                s, e = m.group(1), m.group(2)
                if s:
                    start = int(s); end = int(e) if e else size - 1
                elif e:
                    start = max(0, size - int(e))
                end = min(end, size - 1)
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                code = 206
                extra["Content-Range"] = f"bytes {start}-{end}/{size}"

        ln = end - start + 1
        add_log(ip, "GET", vpath, code, human_size(ln))
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(ln))
        for k, v in extra.items():
            self.send_header(k, v)
        self.end_headers()

        if method == "HEAD" or ln == 0:
            return
        try:
            with open(real, "rb") as f:
                f.seek(start)
                left = ln
                while left > 0:
                    chunk = f.read(min(262144, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---------- 上传 ----------
    def _upload(self, vpath):
        ip = self.client_address[0]
        if not self._has("write"):
            self._json({"ok": False, "msg": "当前权限不允许上传"}, 403)
            return
        real = resolve_path(vpath)
        if not real or not is_allowed(real):
            self._json({"ok": False, "msg": "路径不允许"}, 403)
            return
        os.makedirs(os.path.dirname(real), exist_ok=True)
        total = int(self.headers.get("Content-Length") or 0)
        maxmb = int(CFG.get("max_upload_mb", 0))
        if maxmb and total > maxmb * 1024 * 1024:
            self._json({"ok": False, "msg": f"超过大小限制 {maxmb}MB"}, 413)
            return
        written = 0
        try:
            with open(real, "wb") as f:
                while written < total:
                    chunk = self.rfile.read(min(262144, total - written))
                    if not chunk:
                        break
                    f.write(chunk)
                    written += len(chunk)
        except Exception as e:
            self._json({"ok": False, "msg": str(e)}, 500)
            return
        add_log(ip, "UPLOAD", vpath, 200, human_size(written))
        self._json({"ok": True, "size": written})

    # ---------- 删除 ----------
    def _delete(self, vpath):
        ip = self.client_address[0]
        if not self._has("full"):
            self._json({"ok": False, "msg": "当前权限不允许删除"}, 403)
            return
        real = resolve_path(vpath)
        if not real or not is_allowed(real):
            self._json({"ok": False, "msg": "路径不允许"}, 403)
            return
        try:
            if os.path.isdir(real):
                shutil.rmtree(real)
            else:
                os.remove(real)
        except Exception as e:
            self._json({"ok": False, "msg": str(e)}, 500)
            return
        add_log(ip, "DELETE", vpath, 200)
        self._json({"ok": True})

    # ---------- 重命名 ----------
    def _rename(self):
        ip = self.client_address[0]
        if not self._has("full"):
            self._json({"ok": False, "msg": "当前权限不允许重命名"}, 403)
            return
        ln = int(self.headers.get("Content-Length") or 0)
        data = json.loads(self.rfile.read(ln).decode("utf-8", "ignore") or "{}")
        real = resolve_path(data.get("path", ""))
        newname = (data.get("newname") or "").strip()
        if not real or not is_allowed(real) or not newname:
            self._json({"ok": False, "msg": "参数错误"}, 400)
            return
        target = os.path.join(os.path.dirname(real), newname)
        if not is_allowed(target):
            self._json({"ok": False, "msg": "目标路径不允许"}, 403)
            return
        try:
            os.rename(real, target)
        except Exception as e:
            self._json({"ok": False, "msg": str(e)}, 500)
            return
        add_log(ip, "RENAME", data.get("path", ""), 200)
        self._json({"ok": True})

    # ---------- 新建文件夹 ----------
    def _mkdir(self):
        ip = self.client_address[0]
        if not self._has("write"):
            self._json({"ok": False, "msg": "当前权限不允许新建"}, 403)
            return
        ln = int(self.headers.get("Content-Length") or 0)
        data = json.loads(self.rfile.read(ln).decode("utf-8", "ignore") or "{}")
        real = resolve_path(data.get("path", ""))
        if not real or not is_allowed(real):
            self._json({"ok": False, "msg": "路径不允许"}, 403)
            return
        try:
            os.makedirs(real, exist_ok=True)
        except Exception as e:
            self._json({"ok": False, "msg": str(e)}, 500)
            return
        add_log(ip, "MKDIR", data.get("path", ""), 200)
        self._json({"ok": True})


# ============================================================
# 管理面板 Handler
# ============================================================
class AdminHandler(BaseHTTPRequestHandler):
    server_version = "LanShareAdmin/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False),
                   "application/json; charset=utf-8")

    def _can_admin(self):
        """管理密码为空时，仅允许本机"""
        apwd = CFG.get("admin_password", "")
        ip = self.client_address[0]
        if not apwd:
            return ip in ("127.0.0.1", "::1", "::ffff:127.0.0.1")
        ck = parse_cookies(self.headers.get("Cookie"))
        return ck.get("ls_admin") == expected_token(apwd)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_DELETE(self):
        self._route("DELETE")

    def _route(self, method):
        u = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(u.path)
        qs = urllib.parse.parse_qs(u.query)
        try:
            if path in ("/", "/admin"):
                self._send(200, templates.ADMIN_HTML, "text/html; charset=utf-8")
                return
            if path == "/api/admin/config" and method == "GET":
                if not self._can_admin():
                    self._json({"ok": False, "msg": "无权访问（本机可管理）"}, 403); return
                ips = get_lan_ips()
                self._json({
                    "port": CFG.get("port"), "admin_port": CFG.get("admin_port"),
                    "title": CFG.get("title"), "permission": CFG.get("permission"),
                    "password": CFG.get("password"), "admin_password": CFG.get("admin_password"),
                    "shares": CFG.get("shares", []), "addresses": ips,
                    "qr": gen_qr(f"http://{ips[0]}:{CFG.get('port')}"),
                })
                return
            if path == "/api/admin/config" and method == "POST":
                if not self._can_admin():
                    self._json({"ok": False, "msg": "无权"}, 403); return
                self._save_cfg(); return
            if path == "/api/admin/status":
                self._json({"running": share_running(), "port": CFG.get("port")}); return
            if path == "/api/admin/log":
                if method == "DELETE":
                    with LOG_LOCK: LOGS.clear()
                    self._json({"ok": True}); return
                self._json({"logs": LOGS[:200]}); return
            self._send(404, "Not Found")
        except Exception as e:
            self._json({"ok": False, "msg": str(e)}, 500)

    def _save_cfg(self):
        ln = int(self.headers.get("Content-Length") or 0)
        data = json.loads(self.rfile.read(ln).decode("utf-8", "ignore") or "{}")
        for k in ("permission", "port", "password", "admin_password", "title"):
            if k in data:
                CFG[k] = data[k]
        save_config(CFG)
        self._json({"ok": True, "msg": "已保存"})

    def _admin_api(self, path, method):
        ln = int(self.headers.get("Content-Length") or 0)
        data = json.loads(self.rfile.read(ln).decode("utf-8", "ignore") or "{}") if ln else {}
        if path == "/api/admin/share/add":
            p = (data.get("path") or "").strip()
            if not os.path.isdir(p):
                self._json({"ok": False, "msg": "目录不存在：" + p}); return
            name = os.path.basename(p.rstrip("\\/")) or p
            CFG.setdefault("shares", []).append({"name": name, "path": p})
            save_config(CFG)
            self._json({"ok": True}); return
        if path == "/api/admin/share/del":
            i = int(data.get("index", -1))
            if 0 <= i < len(CFG.get("shares", [])):
                CFG["shares"].pop(i); save_config(CFG)
            self._json({"ok": True}); return
        if path == "/api/admin/service":
            a = data.get("action")
            if a == "start":
                ok, m = start_share()
            elif a == "stop":
                ok, m = stop_share()
            else:
                stop_share(); ok, m = start_share()
            self._json({"ok": ok, "msg": m}); return
        if path == "/api/admin/firewall":
            a = data.get("action", "add")
            msg = firewall(a, [CFG.get("port"), CFG.get("admin_port")])
            self._json({"ok": True, "msg": msg}); return
        if path == "/api/admin/autostart":
            ok, msg = set_autostart(bool(data.get("enable", True)))
            self._json({"ok": ok, "msg": msg}); return
        if path == "/api/admin/openfolder":
            try:
                if os.name == "nt":
                    os.startfile(APP_DIR)
                else:
                    subprocess.Popen(["xdg-open", APP_DIR])
                self._json({"ok": True, "msg": "已打开程序目录"}); return
            except Exception as e:
                self._json({"ok": False, "msg": str(e)}); return
        self._json({"ok": False, "msg": "未知接口"}, 404)

    def do_PUT(self):
        pass

    def do_PATCH(self):
        pass


# 让 POST 的其他管理接口也能进来
_orig_route = AdminHandler._route


def _admin_route(self, method):
    u = urllib.parse.urlparse(self.path)
    path = urllib.parse.unquote(u.path)
    if path.startswith("/api/admin/") and method == "POST" and path not in (
            "/api/admin/config"):
        if not self._can_admin():
            self._json({"ok": False, "msg": "无权（本机可管理）"}, 403)
            return
        self._admin_api(path, method)
        return
    _orig_route(self, method)


AdminHandler._route = _admin_route


# ============================================================
# 服务管理
# ============================================================
_share_server = None
_share_thread = None


def share_running():
    return _share_server is not None


def start_share():
    global _share_server, _share_thread
    if _share_server:
        return False, "共享服务已在运行"
    if not CFG.get("shares"):
        return False, "请先添加至少一个共享目录"
    port = int(CFG.get("port", 8766))

    class Q(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    try:
        _share_server = Q(("0.0.0.0", port), ShareHandler)
    except OSError as e:
        _share_server = None
        return False, f"端口 {port} 被占用或无法绑定：{e}"
    _share_thread = threading.Thread(target=_share_server.serve_forever, daemon=True)
    _share_thread.start()
    return True, f"共享服务已启动（端口 {port}）"


def stop_share():
    global _share_server
    if not _share_server:
        return False, "共享服务未运行"
    try:
        _share_server.shutdown()
        _share_server.server_close()
    except Exception:
        pass
    _share_server = None
    return True, "共享服务已停止"


def add_share(path, name=None):
    """添加/更新共享对象（目录或单个文件），立即生效。返回 (ok, msg)"""
    try:
        path = os.path.abspath(path)
    except Exception as e:
        return False, f"路径不合法: {e}"
    if not os.path.exists(path):
        return False, f"路径不存在: {path}"
    name = name or (os.path.basename(path) or "共享")
    shares = CFG.setdefault("shares", [])
    CFG["shares"] = [s for s in shares
                     if os.path.normpath(s.get("path", "")) != os.path.normpath(path)]
    CFG["shares"].append({"name": name, "path": path})
    if _share_server is None:
        return start_share()
    return True, f"已共享: {path}"


def start_admin():
    """启动管理面板（常驻，不阻塞）。返回 (server, error)"""
    ap = int(CFG.get("admin_port", 8765))

    class A(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    try:
        srv = A(("0.0.0.0", ap), AdminHandler)
    except OSError as e:
        return None, f"管理面板端口 {ap} 被占用：{e}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, None


def launch_android():
    """Android App 入口（由 Chaquopy main.py 调用，非阻塞）。

    - 自动共享公共 Download 目录
    - 自动启动管理面板 + 共享服务
    - 权限默认只读
    """
    for cand in ("/sdcard/Download", "/storage/emulated/0/Download"):
        if os.path.isdir(cand):
            CFG.setdefault("shares", [])
            if not CFG["shares"]:
                CFG["shares"] = [{"name": "Download", "path": cand}]
            break
    CFG["autostart_share"] = True
    CFG["permission"] = "read"
    srv, err = start_admin()
    ok, msg = start_share()
    return (srv is not None), {"admin": err or "ok", "share": msg}


# ============================================================
# 主程序
# ============================================================
def main():
    print("=" * 52)
    print("  LanShare 局域网文件共享")
    print("=" * 52)

    ap = int(CFG.get("admin_port", 8765))
    ips = get_lan_ips()
    print(f"本机地址: {', '.join(ips)}")
    print(f"管理面板: http://127.0.0.1:{ap}/")
    print(f"共享端口: {CFG.get('port')}")
    print(f"共享目录: {len(CFG.get('shares', []))} 个")
    print(f"权限模式: {CFG.get('permission')}")
    print("-" * 52)

    if CFG.get("autostart_share", True):
        ok, m = start_share()
        print(f"[共享服务] {m}")

    srv, err = start_admin()
    if err:
        print(f"[错误] {err}")
        input("按回车退出...")
        return

    if "--no-browser" not in sys.argv:
        try:
            webbrowser.open(f"http://127.0.0.1:{ap}/")
        except Exception:
            pass

    print("管理面板已启动，按 Ctrl+C 或关闭窗口停止服务")
    print("=" * 52)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_share()
        if srv is not None:
            try:
                srv.shutdown()
            except Exception:
                pass
        print("\n已停止")


if __name__ == "__main__":
    main()
