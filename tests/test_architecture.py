import ast
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "app" / "codeforge"


def imports(path: Path) -> Iterable[tuple[int, str]]:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for imported in node.names:
                yield node.lineno, imported.name
        elif isinstance(node, ast.ImportFrom):
            parts = path.relative_to(SOURCE).with_suffix("").parts[:-1]
            if node.level:
                package = ("codeforge", *parts)
                base = ".".join(package[: len(package) - node.level + 1])
                prefix = ".".join(filter(None, (base, node.module)))
            else:
                prefix = node.module or ""
            if node.module:
                yield node.lineno, prefix
            else:
                for imported in node.names:
                    yield node.lineno, f"{prefix}.{imported.name}"


def within(module: str, namespaces: set[str]) -> bool:
    return any(module == path or module.startswith(f"{path}.") for path in namespaces)


@pytest.mark.parametrize("service", ["auth", "education", "contest"])
def test_service_dependencies_point_inward(service: str) -> None:
    root = SOURCE / service
    namespace = f"codeforge.{service}"
    domain = {"codeforge.common.contracts", f"{namespace}.domain"}
    application = domain | {f"{namespace}.application"}
    presentation = application | {
        f"{namespace}.presentation",
        "codeforge.common.http",
        "codeforge.common.security",
        "codeforge.common.runtime",
        "codeforge.common.request_validation",
        "fastapi",
        "pydantic",
    }
    violations = []
    layers = (
        ([root / "domain.py", *(root / "domain").rglob("*.py")], domain),
        (list((root / "application").rglob("*.py")), application),
        (list((root / "presentation").rglob("*.py")), presentation),
    )

    for files, namespaces in layers:
        assert any(path.is_file() and path.stat().st_size for path in files)
        for path in files:
            if not path.is_file():
                continue
            for line, module in imports(path):
                if module.split(".")[0] not in sys.stdlib_module_names and not within(
                    module, namespaces
                ):
                    violations.append(
                        f"{path.relative_to(SOURCE)}:{line} imports {module}"
                    )

    assert not violations, "\n".join(violations)
