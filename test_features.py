import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SERVICE = Path(__file__).parents[1] / "host" / "linux-hotspot-manager-service.py"

def load():
    spec = importlib.util.spec_from_file_location("lhm", SERVICE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def call(mgr, name, *args):
    fn = getattr(mgr, name)
    if hasattr(fn, "__wrapped__"):
        return fn.__wrapped__(mgr, *args)
    return fn(*args)

class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.mod = load()
        self.tmp_dir = tempfile.TemporaryDirectory()
        db_file = Path(self.tmp_dir.name) / "test.sqlite3"
        self.mgr = self.mod.Manager(db_path=db_file)

    def tearDown(self):
        self.mgr.db.close()
        self.tmp_dir.cleanup()

    def test_status(self):
        status = json.loads(call(self.mgr, "GetStatus"))
        self.assertEqual(status["version"], "4.1.0")
        self.assertEqual(status["service"], "ready")

    def test_port_forward_lifecycle(self):
        res = call(self.mgr, "AddPortForward", "tcp", 8080, "10.42.0.50", 80)
        self.assertEqual(res, "saved")
        pfs = json.loads(call(self.mgr, "ListPortForwards"))
        match = [p for p in pfs if p["proto"] == "tcp" and p["listen_port"] == 8080]
        self.assertTrue(len(match) > 0)
        self.assertEqual(match[0]["destination_ip"], "10.42.0.50")
        self.assertEqual(match[0]["destination_port"], 80)

        del_res = call(self.mgr, "DeletePortForward", "tcp", 8080)
        self.assertEqual(del_res, "deleted")
        pfs_after = json.loads(call(self.mgr, "ListPortForwards"))
        self.assertFalse(any(p["proto"] == "tcp" and p["listen_port"] == 8080 for p in pfs_after))

    def test_domain_rules(self):
        call(self.mgr, "AddDomainRule", "badsite.org", "block")
        rules = json.loads(call(self.mgr, "ListDomainRules"))
        self.assertTrue(any(r["domain"] == "badsite.org" and r["action"] == "block" for r in rules))
        call(self.mgr, "RemoveDomainRule", "badsite.org")
        rules_after = json.loads(call(self.mgr, "ListDomainRules"))
        self.assertFalse(any(r["domain"] == "badsite.org" for r in rules_after))

    def test_adblock_status(self):
        call(self.mgr, "SetAdblockEnabled", True)
        st = json.loads(call(self.mgr, "GetAdblockStatus"))
        self.assertTrue(st["enabled"])
        call(self.mgr, "SetAdblockEnabled", False)
        st2 = json.loads(call(self.mgr, "GetAdblockStatus"))
        self.assertFalse(st2["enabled"])

    def test_url_logs(self):
        self.mgr.db.execute("INSERT INTO url_logs(ts, mac, ip, url) VALUES(?,?,?,?)",
                            (123456, "aa:bb:cc:dd:ee:ff", "10.42.0.2", "google.com"))
        self.mgr.db.commit()
        logs = json.loads(call(self.mgr, "GetUrlLog", 10))
        self.assertTrue(any(l["url"] == "google.com" for l in logs))
        call(self.mgr, "ClearUrlLogs")
        logs_empty = json.loads(call(self.mgr, "GetUrlLog", 10))
        self.assertEqual(len(logs_empty), 0)

if __name__ == "__main__":
    unittest.main()
