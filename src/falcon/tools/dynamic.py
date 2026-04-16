from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import ast
import hashlib
import json
import sys
import textwrap

from falcon.tools.runner import ExternalCommandError, run_external_command


DEFAULT_ALLOWED_IMPORTS = {
    "Bio",
    "collections",
    "csv",
    "itertools",
    "json",
    "math",
    "re",
    "statistics",
}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "open"}
FORBIDDEN_METHODS = {"write", "write_text", "write_bytes", "open", "mkdir", "unlink", "rename", "replace"}


@dataclass(frozen=True)
class DynamicScriptValidation:
    approved: bool
    errors: list[str]


def validate_dynamic_python_script(
    script_source: str,
    *,
    allowed_imports: set[str] | None = None,
) -> DynamicScriptValidation:
    allowed = allowed_imports or DEFAULT_ALLOWED_IMPORTS
    errors: list[str] = []
    try:
        tree = ast.parse(script_source)
    except SyntaxError as exc:
        return DynamicScriptValidation(False, [f"syntax error: {exc}"])

    has_run = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for module_name in _imported_roots(node):
                if module_name not in allowed:
                    errors.append(f"import not allowed: {module_name}")
        elif isinstance(node, ast.FunctionDef) and node.name == "run":
            has_run = True
        elif isinstance(node, ast.Call):
            call_name = _call_name(node.func)
            if call_name in FORBIDDEN_CALLS or call_name.split(".", 1)[0] in {"subprocess", "socket"}:
                errors.append(f"call not allowed: {call_name}")
            if call_name.rsplit(".", 1)[-1] in FORBIDDEN_METHODS:
                errors.append(f"call not allowed: {call_name}")
    if not has_run:
        errors.append("script must define run(input_payload: dict) -> dict")
    return DynamicScriptValidation(not errors, sorted(set(errors)))


class DynamicPythonToolRunner:
    def __init__(
        self,
        *,
        output_dir: Path | str,
        log_dir: Path | str,
        python_executable: Path | str | None = None,
        timeout_seconds: float = 60,
        allowed_imports: set[str] | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.log_dir = Path(log_dir)
        self.python_executable = str(python_executable or sys.executable)
        self.timeout_seconds = float(timeout_seconds)
        self.allowed_imports = allowed_imports or DEFAULT_ALLOWED_IMPORTS

    def run(self, *, script_source: str, input_payload: dict[str, Any], label: str) -> dict[str, Any]:
        validation = validate_dynamic_python_script(script_source, allowed_imports=self.allowed_imports)
        script_hash = hashlib.sha256(script_source.encode("utf-8")).hexdigest()
        safe_label = _safe_label(label)
        tool_dir = self.output_dir / f"{safe_label}-{script_hash[:12]}"
        tool_dir.mkdir(parents=True, exist_ok=True)
        script_path = tool_dir / "tool_module.py"
        wrapper_path = tool_dir / "runner.py"
        input_path = tool_dir / "input.json"
        output_path = tool_dir / "output.json"
        script_path.write_text(script_source, encoding="utf-8")
        input_path.write_text(json.dumps(input_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if not validation.approved:
            return {
                "tool": "dynamic_python",
                "status": "rejected",
                "reason": "dynamic script failed validation",
                "validation_errors": validation.errors,
                "script_sha256": script_hash,
                "script_path": str(script_path),
                "input_path": str(input_path),
                "output_path": str(output_path),
            }

        wrapper_path.write_text(_wrapper_source(), encoding="utf-8")
        try:
            trace = run_external_command(
                command=[self.python_executable, str(wrapper_path), str(script_path), str(input_path), str(output_path)],
                log_dir=self.log_dir,
                label=f"dynamic-{safe_label}",
                timeout_seconds=self.timeout_seconds,
            )
        except ExternalCommandError as exc:
            return {
                "tool": "dynamic_python",
                "status": "error",
                "reason": str(exc),
                "trace": exc.trace,
                "script_sha256": script_hash,
                "script_path": str(script_path),
                "input_path": str(input_path),
                "output_path": str(output_path),
            }

        try:
            result = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "tool": "dynamic_python",
                "status": "error",
                "reason": f"dynamic script did not write valid JSON: {exc}",
                "trace": trace,
                "script_sha256": script_hash,
                "script_path": str(script_path),
                "input_path": str(input_path),
                "output_path": str(output_path),
            }
        return {
            "tool": "dynamic_python",
            "status": str(result.get("status") or "ok") if isinstance(result, dict) else "ok",
            "result": result,
            "trace": trace,
            "script_sha256": script_hash,
            "script_path": str(script_path),
            "input_path": str(input_path),
            "output_path": str(output_path),
        }


def _imported_roots(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name.split(".", 1)[0] for alias in node.names]
    if node.module is None:
        return []
    return [node.module.split(".", 1)[0]]


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _wrapper_source() -> str:
    return textwrap.dedent(
        """
        from __future__ import annotations

        import importlib.util
        import json
        import sys

        module_path, input_path, output_path = sys.argv[1:4]
        spec = importlib.util.spec_from_file_location("dynamic_tool_module", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with open(input_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        result = module.run(payload)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\\n")
        """
    ).lstrip()


def _safe_label(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "-" for char in value).strip("-") or "dynamic-tool"
