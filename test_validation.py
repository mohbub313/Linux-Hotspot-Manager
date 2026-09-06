import re, unittest
MAC_RE=re.compile(r'^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$')
class ValidationTests(unittest.TestCase):
    def test_mac(self):
        self.assertTrue(MAC_RE.fullmatch('AA:BB:CC:DD:EE:FF'))
        self.assertFalse(MAC_RE.fullmatch('AA:BB:CC'))
if __name__ == '__main__': unittest.main()
