"""Test YouTube upload không truyền cả http và credentials vào build().

Bug v1.5.0-v1.8.0: build("youtube","v3", credentials=creds,
http=httplib2.Http(...)) -> google báo "Arguments http and credentials
are mutually exclusive", mọi lượt đăng YouTube đều thất bại.

Chạy:  python -m unittest discover   (từ thư mục project)
"""
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp(prefix="su_test_ytbuild_")
os.environ["SOCIAL_UPLOADER_DB"] = os.path.join(_tmp, "data.db")

_built_kwargs = {}


def _make_module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


class _FakeCreds:
    valid = True


def _fake_build(service, version, **kwargs):
    _built_kwargs.clear()
    _built_kwargs.update(kwargs)

    class _Insert:
        def next_chunk(self):
            return None, {"id": "vid123"}

    class _Videos:
        def insert(self, **kw):
            return _Insert()

    class _Service:
        def videos(self):
            return _Videos()

    return _Service()


def _setUp_stubs():
    disc = _make_module("googleapiclient.discovery", build=_fake_build)
    _make_module("googleapiclient",
                 discovery=disc, http=types.ModuleType("ghttp"))
    _make_module("googleapiclient.http",
                 MediaFileUpload=lambda *a, **k: object())
    gauth = _make_module("google_auth_httplib2")
    gauth.AuthorizedHttp = lambda creds, http=None: http  # trả về http
    h2 = _make_module("httplib2")
    h2.Http = lambda timeout=None: types.SimpleNamespace(timeout=timeout)
    # _get_credentials: stub google.auth + secrets có sẵn token
    tr = _make_module("google.auth.transport.requests", Request=object)
    _make_module("google.auth.transport", requests=tr)
    _make_module("google.auth", transport=tr)
    oc = _make_module("google.oauth2.credentials")
    oc.Credentials = _CredsStub
    _make_module("google.oauth2", credentials=oc)


class _CredsStub:
    expired = False
    refresh_token = ""
    valid = True

    @classmethod
    def from_authorized_user_info(cls, info, scopes):
        return cls()

    def to_json(self):
        return "{}"


_setUp_stubs()

from app.platforms import youtube as yt  # noqa: E402
from app.core import secrets as secrets_mod  # noqa: E402


class TestYouTubeBuildArgs(unittest.TestCase):
    def test_no_mutually_exclusive_args(self):
        secrets_mod.set_secret("youtube_token_json",
                               '{"client_id":"x"}')
        plat = yt.YouTubePlatform()
        # _get_credentials cần raw JSON parse được -> dùng stub trực tiếp
        plat._get_credentials = lambda: _FakeCreds()
        import tempfile as _tf
        with _tf.NamedTemporaryFile(suffix=".mp4",
                                    delete=False) as f:
            f.write(b"0" * 1024)
            path = f.name
        try:
            res = plat.upload(
                {"file_path": path, "title": "t",
                 "scheduled_at": "2099-01-01T10:00:00",
                 "thumbnail_path": ""}, lambda p: None)
        finally:
            os.unlink(path)
        self.assertTrue(res.ok, f"upload thất bại: {res.error}")
        self.assertNotIn("credentials", _built_kwargs,
                         "build() không được nhận cả credentials và http")
        # AuthorizedHttp bọc http có timeout -> http được truyền vào build
        self.assertIn("http", _built_kwargs)


if __name__ == "__main__":
    unittest.main()


class TestFacebookBinaryMethod(unittest.TestCase):
    def test_transfer_uses_post(self):
        from app.platforms import facebook as fb
        calls = {}

        class _Resp:
            status_code = 200

            def json(self):
                return {"success": True}

        orig_post, orig_put = fb.requests.post, fb.requests.put

        def _fake_post(*a, **k):
            calls["post"] = (a, k)
            return _Resp()

        def _fake_put(*a, **k):
            calls["put"] = (a, k)
            return _Resp()

        fb.requests.post, fb.requests.put = _fake_post, _fake_put
        try:
            import tempfile as _tf
            with _tf.NamedTemporaryFile(suffix=".mp4",
                                        delete=False) as f:
                f.write(b"0" * 1024)
                path = f.name
            try:
                plat = fb.FacebookPlatform()
                plat._put_binary("https://example.com/up", "tok",
                                path, lambda p: None)
            finally:
                os.unlink(path)
        finally:
            fb.requests.post, fb.requests.put = orig_post, orig_put
        self.assertIn("post", calls,
                      "phase transfer phải dùng POST theo docs của Meta")
        self.assertNotIn("put", calls)
