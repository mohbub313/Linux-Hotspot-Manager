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

def test_domain_validation():
    m = load()
    assert m._valid_domain("example.com")
    assert m._valid_domain("www.example.com")
    assert not m._valid_domain("localhost")
    assert not m._valid_domain("bad domain.com")

def test_domain_files(monkeypatch, tmp_path):
    m = load()
    monkeypatch.setattr(m, "_dns_block_file", lambda: str(tmp_path / "blocked"))
    monkeypatch.setattr(m, "_dns_allow_file", lambda: str(tmp_path / "allowed"))
    b, a = m._write_domain_lists(["Example.com", "*.example.org"], ["safe.example.com"])
    assert b == ["example.com", "example.org"]
    assert a == ["safe.example.com"]
    assert "address=/example.com/" in (tmp_path / "blocked").read_text()

class DnsFilterTests(unittest.TestCase):
    def test_domain_validation(self):
        m = load()
        self.assertTrue(m._valid_domain("example.com"))
        self.assertTrue(m._valid_domain("www.example.com"))
        self.assertFalse(m._valid_domain("localhost"))
        self.assertFalse(m._valid_domain("bad domain.com"))

    def test_domain_files(self):
        m = load()
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            blocked_file = tmp / "blocked"
            allowed_file = tmp / "allowed"
            with patch.object(m, "_dns_block_file", return_value=str(blocked_file)), \
                 patch.object(m, "_dns_allow_file", return_value=str(allowed_file)):
                b, a = m._write_domain_lists(["Example.com", "*.example.org"], ["safe.example.com"])
                self.assertEqual(b, ["example.com", "example.org"])
                self.assertEqual(a, ["safe.example.com"])
                self.assertIn("address=/example.com/", blocked_file.read_text())

if __name__ == "__main__":
    unittest.main()
