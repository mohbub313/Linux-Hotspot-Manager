import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SERVICE = Path(__file__).parents[1] / "host" / "linux-hotspot-manager-service.py"

def load_module():
    spec = importlib.util.spec_from_file_location("lhm_service", SERVICE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_mac_validation():
    mod = load_module()
    assert mod._valid_mac("AA:BB:CC:DD:EE:FF")
    assert not mod._valid_mac("AA:BB:CC:DD:EE")

def test_parse_client_counters(monkeypatch):
    mod = load_module()
    monkeypatch.setattr(mod, "_nft_json", lambda: {"nftables": [
        {"rule": {"comment": "lhm:aa:bb:cc:dd:ee:ff:upload",
                   "expr": [{"match": {"left": "iifname", "right": "wlan0"}},
                            {"counter": {"packets": 10, "bytes": 1000}}]}},
        {"rule": {"comment": "lhm:aa:bb:cc:dd:ee:ff:download",
                   "expr": [{"match": {"left": "oifname", "right": "wlan0"}},
                            {"counter": {"packets": 20, "bytes": 2000}}]}}
    ]})
    assert mod._parse_client_counters("wlan0") == [{
        "mac": "aa:bb:cc:dd:ee:ff",
        "rx_bytes": 2000, "tx_bytes": 1000,
        "packets_rx": 20, "packets_tx": 10
    }]

class ClientTrafficTests(unittest.TestCase):
    def test_mac_validation(self):
        mod = load_module()
        self.assertTrue(mod._valid_mac("AA:BB:CC:DD:EE:FF"))
        self.assertFalse(mod._valid_mac("AA:BB:CC:DD:EE"))

    def test_parse_client_counters(self):
        mod = load_module()
        fake = {"nftables": [
            {"rule": {"comment": "lhm:aa:bb:cc:dd:ee:ff:upload",
                       "expr": [{"match": {"left": "iifname", "right": "wlan0"}},
                                {"counter": {"packets": 10, "bytes": 1000}}]}},
            {"rule": {"comment": "lhm:aa:bb:cc:dd:ee:ff:download",
                       "expr": [{"match": {"left": "oifname", "right": "wlan0"}},
                                {"counter": {"packets": 20, "bytes": 2000}}]}}
        ]}
        with patch.object(mod, "_nft_json", return_value=fake):
            self.assertEqual(mod._parse_client_counters("wlan0"), [{
                "mac": "aa:bb:cc:dd:ee:ff",
                "rx_bytes": 2000, "tx_bytes": 1000,
                "packets_rx": 20, "packets_tx": 10
            }])

if __name__ == "__main__":
    unittest.main()
