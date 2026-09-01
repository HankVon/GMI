"""
单位机前端托管 + API 反向代理(纯 Python 标准库, 零额外依赖)。
- 托管 frontend/dist 静态文件(SPA: 未知路径回退 index.html)
- 把 /api 反向代理到 backend 容器(http://backend:8000), 实现同源, 避免 CORS
用法(容器内): python serve.py
"""
import os
import re
import gzip
import io
import urllib.request
import urllib.error
from http.server import HTTPServer, ThreadingHTTPServer, SimpleHTTPRequestHandler

DIST_DIR = os.environ.get("DIST_DIR", "/app/dist")
BACKEND_TARGET = os.environ.get("BACKEND_TARGET", "http://backend:8000")
PORT = int(os.environ.get("PORT", "80"))
# 带内容hash的静态资源(js/css/字体/图片)可长缓存: 文件名变化即失效, 无需担心更新不生效
_HASH_RE = re.compile(r"-[A-Za-z0-9_-]{8,}\.(?:js|css|woff2?|ttf|eot|png|jpg|jpeg|svg|webp|gif)$", re.I)
# 可 gzip 压缩的文本资源(域名走 Cloudflare 免费隧道带宽窄, gzip 能省 70-80% 传输体积)
_GZIP_RE = re.compile(r"\.(?:js|css|html|json|svg|txt)$", re.I)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def end_headers(self):
        # 带hash静态资源: 长缓存(immutable), 避免每页重复下载大JS(如 element-plus 1MB)
        # index.html / 无hash资源: 禁用缓存, 保证每次访问拉最新
        p = self.path.split("?")[0]
        if p == "/index.html" or p == "/":
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        elif _HASH_RE.search(p):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _client_accepts_gzip(self) -> bool:
        enc = self.headers.get("Accept-Encoding", "")
        return "gzip" in enc.lower()

    def _serve_with_gzip(self, fpath: str):
        """对文本类静态资源(js/css/svg/json)启用 gzip 传输, 大幅降低窄带宽下载耗时。"""
        if not _GZIP_RE.search(fpath) or not self._client_accepts_gzip():
            return False
        try:
            with open(fpath, "rb") as f:
                raw = f.read()
        except OSError:
            return False
        if len(raw) < 500:
            return False
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6, mtime=0) as gz:
            gz.write(raw)
        comp = buf.getvalue()
        self.send_response(200)
        self.send_header("Content-type", self.guess_type(fpath))
        self.send_header("Content-Length", str(len(comp)))
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Vary", "Accept-Encoding")
        self.end_headers()
        self.wfile.write(comp)
        return True

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy("GET")
        else:
            # SPA: 文件不存在则回退 index.html
            fpath = os.path.join(DIST_DIR, self.path.lstrip("/").split("?")[0])
            if self.path == "/" or not os.path.exists(fpath) or os.path.isdir(fpath):
                self.path = "/index.html"
            # 优先 gzip 压缩文本资源
            if _GZIP_RE.search(self.path.split("?")[0]) and self._serve_with_gzip(fpath):
                return
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy("POST")
        else:
            self.send_error(405)

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self._proxy("PUT")
        else:
            self.send_error(405)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self._proxy("DELETE")
        else:
            self.send_error(405)

    def _proxy(self, method):
        target = BACKEND_TARGET + self.path
        length = int(self.headers.get("Content-Length", 0)) if self.headers.get("Content-Length") else 0
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(target, data=body, method=method)
        # 透传请求头(去掉 host)
        for k in self.headers.keys():
            if k.lower() not in ("host", "content-length"):
                req.add_header(k, self.headers[k])
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:  # noqa
            self.send_error(502, f"Bad gateway: {e}")

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    os.makedirs(DIST_DIR, exist_ok=True)
    print(f"[serve] serving {DIST_DIR} on :{PORT}, proxy /api -> {BACKEND_TARGET}")
    # 多线程: 并发传输多个静态资源, 避免单线程下多资源排队导致页面加载慢
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
