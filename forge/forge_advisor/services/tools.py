import subprocess
import sys
import time
from pathlib import Path

from langchain.tools import tool

from forge_advisor.services.project import (
    IGNORED_DIRS,
    iter_files,
    safe_path,
)

PROTECTED_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
}

PROTECTED_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
MAX_WRITE_BYTES = 250_000
MAX_READ_BYTES = 100_000


def _is_protected(path: Path) -> bool:
    return (
        path.name in PROTECTED_NAMES
        or path.suffix.lower() in PROTECTED_SUFFIXES
        or any(part in {"secrets", "credentials"} for part in path.parts)
    )


def build_read_only_tools(project_root: str):
    @tool
    def list_files() -> str:
        """List relevant text/source files in the repository. Read-only."""
        root = Path(project_root).resolve()
        files = [
            str(path.relative_to(root))
            for path in iter_files(project_root)
        ]
        return "\n".join(files[:500]) or "No relevant files found."

    @tool
    def read_file(path: str) -> str:
        """Read a UTF-8 text file inside the repository. Read-only."""
        target = safe_path(project_root, path)
        if not target.is_file():
            return f"File does not exist: {path}"
        if target.stat().st_size > MAX_READ_BYTES:
            return f"File is larger than the safe read limit ({MAX_READ_BYTES} bytes): {path}"
        if _is_protected(target):
            return f"Access denied for protected file: {path}"
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"File is not UTF-8 text: {path}"

    @tool
    def git_status() -> str:
        """Return git status for the repository. Read-only."""
        try:
            completed = subprocess.run(
                ["git", "status", "--short"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except FileNotFoundError:
            return "git executable is not available"
        except subprocess.TimeoutExpired:
            return "git status timed out"

        if completed.returncode != 0:
            return completed.stderr.strip() or "Not a git repository"
        return completed.stdout.strip() or "Working tree clean"

    return [list_files, read_file, git_status]


def build_implementation_tools(project_root: str):
    tools = list(build_read_only_tools(project_root))

    @tool
    def write_file(path: str, content: str) -> str:
        """Write UTF-8 text to a file inside the repository after human approval."""
        target = safe_path(project_root, path)

        if _is_protected(target):
            return f"Refused to write protected file: {path}"

        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            return f"Refused: file exceeds {MAX_WRITE_BYTES} bytes"

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {path}"

    @tool
    def run_tests(test_target: str = "") -> str:
        """Run pytest only. Optional test_target must be a path inside the repository."""
        target = ""
        if test_target.strip():
            candidate = safe_path(project_root, test_target.strip())
            if not candidate.exists():
                return f"Test target does not exist: {test_target}"
            target = str(candidate.relative_to(Path(project_root).resolve()))

        command = [sys.executable, "-m", "pytest", "-q"]
        if target:
            command.append(target)

        try:
            completed = subprocess.run(
                command,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "pytest timed out after 90 seconds"
        except FileNotFoundError as exc:
            return f"Unable to execute pytest: {exc}"

        output = (completed.stdout + "\n" + completed.stderr).strip()
        return f"exit_code={completed.returncode}\n{output[-12000:]}"

    tools.append(write_file)
    tools.append(run_tests)
    return tools
