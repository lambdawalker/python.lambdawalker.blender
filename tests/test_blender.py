import ast
import pathlib
import re
import sys
import tomllib
from unittest.mock import MagicMock

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = "blender"
SRC_DIR = ROOT / "src" / "lambdawalker" / MODULE


def test_pep420_namespace_layout():
    assert SRC_DIR.exists(), f"Expected module directory {SRC_DIR}"
    assert not (ROOT / "src" / "lambdawalker" / "__init__.py").exists(), (
        "src/lambdawalker/__init__.py must not exist in PEP 420 namespace package"
    )


def test_ast_syntax_and_compile():
    py_files = list(SRC_DIR.rglob("*.py"))
    assert py_files, f"No Python files found in {SRC_DIR}"
    for path in py_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        compile(tree, filename=str(path), mode="exec")


def test_undeclared_internal_dependencies():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared_deps = {
        re.split(r"[><=~!;\s]", d)[0] for d in pyproject.get("project", {}).get("dependencies", [])
    }
    uv_sources = set(pyproject.get("tool", {}).get("uv", {}).get("sources", {}).keys())

    imported_internal = set()
    for path in SRC_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if len(parts) >= 2 and parts[0] == "lambdawalker" and parts[1] != MODULE:
                        imported_internal.add(f"lambdawalker-{parts[1]}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 2 and parts[0] == "lambdawalker" and parts[1] != MODULE:
                    imported_internal.add(f"lambdawalker-{parts[1]}")

    missing_deps = imported_internal - declared_deps
    missing_sources = imported_internal - uv_sources
    assert not missing_deps, f"Undeclared internal dependencies in [project].dependencies: {missing_deps}"
    assert not missing_sources, f"Missing SSH git sources in [tool.uv.sources]: {missing_sources}"


def test_static_security_and_bug_patterns():
    findings = []
    for path in SRC_DIR.rglob("*.py"):
        rel = path.relative_to(ROOT)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    findings.append(f"{rel}:{node.lineno} calls {node.func.id}()")
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        findings.append(f"{rel}:{node.lineno} subprocess call with shell=True")

    assert not findings, "Security / packaging issues detected:\n" + "\n".join(findings)


def test_blender_modules_with_mocked_bpy(monkeypatch):
    monkeypatch.setitem(sys.modules, "bpy", MagicMock())
    monkeypatch.setitem(sys.modules, "bmesh", MagicMock())
    monkeypatch.setitem(sys.modules, "mathutils", MagicMock())
    from lambdawalker.blender import find_materials, purge_orphan_data
    assert find_materials is not None
    assert purge_orphan_data is not None
