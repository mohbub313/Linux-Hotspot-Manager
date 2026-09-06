import ast, pathlib, unittest

ROOT=pathlib.Path(__file__).parents[1]
class SecurityTests(unittest.TestCase):
    def test_host_has_no_shell_true(self):
        tree=ast.parse((ROOT/'host/linux-hotspot-manager-service.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == 'run':
                    for kw in node.keywords:
                        if kw.arg == 'shell' and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            self.fail('shell=True found')
    def test_passwords_are_not_literal_logged(self):
        text=(ROOT/'portal/server.py').read_text()
        self.assertNotIn('print(form)',text)
if __name__=='__main__': unittest.main()
