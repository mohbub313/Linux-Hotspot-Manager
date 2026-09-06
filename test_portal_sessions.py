import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SERVICE = Path(__file__).parents[1] / "host" / "linux-hotspot-manager-service.py"

def load():
    spec = importlib.util.spec_from_file_location("lhm", SERVICE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_session_roundtrip(monkeypatch, tmp_path):
    m = load()
    p = tmp_path / "sessions.json"
    monkeypatch.setattr(m, "_portal_session_path", lambda: p)
    token = m._portal_session_token()
    m._save_portal_sessions({"aa:bb:cc:dd:ee:ff": {
        "token": token, "authenticated": True, "expires_at": 9999999999
    }})
    assert m._portal_session_valid("aa:bb:cc:dd:ee:ff", token)
    assert not m._portal_session_valid("aa:bb:cc:dd:ee:ff", "wrong")

class PortalSessionTests(unittest.TestCase):
    def test_session_roundtrip(self):
        m = load()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sessions.json"
            with patch.object(m, "_portal_session_path", return_value=p):
                token = m._portal_session_token()
                m._save_portal_sessions({"aa:bb:cc:dd:ee:ff": {
                    "token": token, "authenticated": True, "expires_at": 9999999999
                }})
                self.assertTrue(m._portal_session_valid("aa:bb:cc:dd:ee:ff", token))
                self.assertFalse(m._portal_session_valid("aa:bb:cc:dd:ee:ff", "wrong"))

if __name__ == "__main__":
    unittest.main()
