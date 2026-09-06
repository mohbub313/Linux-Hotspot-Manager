from pathlib import Path
import xml.etree.ElementTree as ET
import unittest

ROOT = Path(__file__).parents[1]

def test_polkit_policy_is_valid_xml():
    policies = list((ROOT / "polkit").glob("*.policy"))
    assert policies
    root = ET.parse(policies[0]).getroot()
    actions = {a.attrib["id"] for a in root.findall("action")}
    assert "org.shazid.LinuxHotspotManager.network" in actions
    assert "org.shazid.LinuxHotspotManager.clients" in actions

class PolkitTests(unittest.TestCase):
    def test_polkit_policy_is_valid_xml(self):
        policies = list((ROOT / "polkit").glob("*.policy"))
        self.assertTrue(bool(policies))
        root = ET.parse(policies[0]).getroot()
        actions = {a.attrib["id"] for a in root.findall("action")}
        self.assertIn("org.shazid.LinuxHotspotManager.network", actions)
        self.assertIn("org.shazid.LinuxHotspotManager.clients", actions)

if __name__ == "__main__":
    unittest.main()
