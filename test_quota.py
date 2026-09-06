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

def test_quota_state(monkeypatch, tmp_path):
    m = load()
    p = tmp_path / "quota.json"
    monkeypatch.setattr(m, "_quota_state_path", lambda: p)
    m._save_quota_state({"aa:bb:cc:dd:ee:ff": {"quota_bytes": 100}})
    assert m._load_quota_state()["aa:bb:cc:dd:ee:ff"]["quota_bytes"] == 100

class QuotaTests(unittest.TestCase):
    def test_quota_state(self):
        m = load()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "quota.json"
            with patch.object(m, "_quota_state_path", return_value=p):
                m._save_quota_state({"aa:bb:cc:dd:ee:ff": {"quota_bytes": 100}})
                self.assertEqual(m._load_quota_state()["aa:bb:cc:dd:ee:ff"]["quota_bytes"], 100)

if __name__ == "__main__":
    unittest.main()
