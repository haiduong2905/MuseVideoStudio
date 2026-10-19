"""Local OAuth callback server dùng chung cho YouTube và TikTok.

Vấn đề gốc: ``flow.run_local_server()`` và ``thread.join()`` chạy ngay trên
luồng giao diện -> app treo cứng "Not Responding" khi chờ user xác thực trên
trình duyệt. Module này tách server ra để:

- chạy trên luồng nền (caller tự quyết định thread),
- chờ code có **timeout**,
- **hủy được** giữa chừng qua ``threading.Event`` (nút Hủy trên dialog).

Chỉ dùng stdlib nên test được mà không cần google-auth hay PySide6.
"""
import http.server
import threading
from typing import Optional
from urllib.parse import parse_qs, urlparse

SUCCESS_HTML = (
    "<html><body style='font-family:sans-serif;text-align:center;"
    "padding-top:60px'>"
    "<h2>✅ Đã nhận mã xác thực</h2>"
    "<p>Bạn có thể đóng tab này và quay lại app.</p>"
    "</body></html>"
).encode("utf-8")


class OAuthCodeServer:
    """HTTP server nhỏ trên 127.0.0.1, hứng ?code= / ?error= rồi thôi."""

    def __init__(self, port: int = 0) -> None:
        """port=0: cổng ngẫu nhiên (YouTube chấp nhận mọi cổng localhost).
        TikTok bắt buộc đúng cổng đã đăng ký (8765) nên truyền port=8765.
        """
        self._bind_port = port
        self.code: Optional[str] = None
        self.error: Optional[str] = None
        self._server: Optional[http.server.HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def port(self) -> int:
        if not self._server:
            raise RuntimeError("Server chưa start.")
        return self._server.server_address[1]

    @property
    def redirect_uri(self) -> str:
        return f"http://localhost:{self.port}/callback"

    def start(self) -> None:
        outer = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                qs = parse_qs(urlparse(self.path).query)
                outer.code = (qs.get("code") or [None])[0]
                outer.error = (qs.get("error") or [None])[0]
                if not outer.code and not outer.error:
                    # Google đôi khi GET /favicon.ico trước
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type",
                                 "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(SUCCESS_HTML)

            def log_message(self, *args):  # tắt log http.server
                pass

        self._server = http.server.HTTPServer(
            ("127.0.0.1", self._bind_port), _Handler)
        # timeout để serve_forever kiểm tra cờ dừng định kỳ
        self._server.timeout = 0.5
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        daemon=True,
                                        name="oauth-callback")
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None


def wait_for_code(server: OAuthCodeServer, timeout: float,
                  cancel_event: Optional[threading.Event] = None
                  ) -> tuple[Optional[str], Optional[str]]:
    """Chờ code tới khi: có code/error, hết timeout, hoặc cancel_event set.

    Trả về (code, error). Cả hai None = timeout hoặc bị hủy.
    """
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cancel_event is not None and cancel_event.is_set():
            return None, None
        if server.code or server.error:
            return server.code, server.error
        time.sleep(0.2)
    return None, None
