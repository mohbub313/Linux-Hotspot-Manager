import unittest, pathlib
class TrafficTests(unittest.TestCase):
    def test_stats_paths_are_sysfs(self):
        text=(pathlib.Path(__file__).parents[1]/'host/linux-hotspot-manager-service.py').read_text()
        self.assertIn('/sys/class/net', text)
        self.assertIn('GetTrafficStats', text)
if __name__=='__main__': unittest.main()
