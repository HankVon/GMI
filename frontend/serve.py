"""
单位机前端托管 + API 反向代理(纯 Python 标准库, 零额外依赖)。
- 托管 frontend/dist 静态文件(SPA: 未知路径回退 index.html)
- 把 /api 反向代理到 backend 容器(http://backend:8000), 实现同源, 避免 CORS
用法(容器内): python serve.py
"""
import os
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

DIST_DIR = os.environ.get("DIST_DIR", "/app/dist")
BACKEND_TARGET = os.environ.get("BACKEND_TARGET", "http://backend:8000")
PORT = int(os.environ.get("PORT", "80"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy("GET")
        else:
            # SPA: 文件不存在则回退 index.html
            fpath = os.path.join(DIST_DIR, self.path.lstrip("/").split("?")[0])
            if self.path == "/" or not os.path.exists(fpath) or os.path.isdir(fpath):
                self.path = "/index.html"
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
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
