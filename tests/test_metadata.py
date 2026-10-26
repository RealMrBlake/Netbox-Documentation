import ast
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]


def plugin_versions():
    tree = ast.parse((ROOT / "netbox_documentation" / "__init__.py").read_text())
    config = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    values = {
        target.id: node.value.value
        for node in config.body if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
        for target in node.targets if isinstance(target, ast.Name)
    }
    return values["min_version"], values["max_version"]


def test_readme_matches_plugin_version_range():
    minimum, maximum = plugin_versions()
    expected = f"`{minimum}` – `{'.'.join(maximum.split('.')[:2])}.x`"
    readme = (ROOT / "README.md").read_text()
    assert re.search(rf"\| \*\*NetBox\*\* \| {re.escape(expected)} \|", readme)
    assert f"- NetBox {expected}" in readme
