"""Dialog Hướng dẫn sử dụng — hiển thị HUONG-DAN.md ngay trong app."""
import os
import sys

from PySide6.QtWidgets import (QDialog, QPushButton, QTextBrowser, QVBoxLayout)


def _guide_path() -> str | None:
    """Tìm file HUONG-DAN.md (cả khi chạy dev lẫn khi đã đóng gói)."""
    candidates = []
    if getattr(sys, "frozen", False):
        # PyInstaller onedir: file nằm cạnh exe
        candidates.append(
            os.path.join(os.path.dirname(sys.executable), "HUONG-DAN.md"))
    # chạy dev: project root (2 cấp trên app/ui)
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(
        os.path.dirname(os.path.dirname(here)), "HUONG-DAN.md"))
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _markdown_to_html(text: str) -> str:
    """Chuyển markdown sang HTML. Ưu tiên lib `markdown`, fallback tối giản."""
    try:
        import markdown as md_lib
        return md_lib.markdown(text, extensions=["extra"])
    except ImportError:
        pass
    # fallback: giữ nguyên text, chỉ xuống dòng
    import html as html_lib
    body = html_lib.escape(text).replace("\n", "<br>")
    return f"<pre style='white-space: pre-wrap;'>{body}</pre>"


def _wrap_html(html: str) -> str:
    """Bọc HTML bằng style hợp với theme tối của QTextBrowser.

    (Trước đây code/pre để nền sáng #f0f0f0 trong khi chữ bị theme ép
    màu sáng -> chữ tàng hình trên nền sáng.)
    """
    return (
        "<style>"
        "body{font-size:14px; line-height:1.6; color:#e2e8f0;}"
        "h1,h2,h3{color:#ffffff;}"
        "a{color:#93c5fd;}"
        "code{background:#1e293b; color:#fcd34d; padding:2px 6px;}"
        "pre{background:#1e293b; color:#e2e8f0; padding:10px;}"
        "blockquote{color:#94a3b8; border-left:3px solid #4f46e5; "
        "margin-left:0; padding-left:12px;}"
        "</style>" + html
    )


class HelpDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hướng dẫn sử dụng")
        self.resize(760, 600)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)

        path = _guide_path()
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    md = f.read()
                html = _markdown_to_html(md)
                self.view.setHtml(_wrap_html(html))
            except OSError as exc:
                self.view.setPlainText(f"Không đọc được file hướng dẫn: {exc}")
        else:
            self.view.setPlainText(
                "Không tìm thấy file HUONG-DAN.md.\n"
                "Hãy đảm bảo file nằm cùng thư mục với app.")

        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.accept)

        lay = QVBoxLayout(self)
        lay.addWidget(self.view)
        lay.addWidget(close_btn)
