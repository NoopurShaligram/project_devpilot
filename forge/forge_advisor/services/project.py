from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".forge",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

INSTRUCTION_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "architecture.md",
    "ARCHITECTURE.md",
    "CONTRIBUTING.md",
    ".cursorrules",
)


def resolve_project_root(project_root: str) -> Path:
    root = Path(project_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Project root does not exist or is not a directory: {root}")
    return root


def safe_path(project_root: str, relative_path: str) -> Path:
    root = resolve_project_root(project_root)
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path escapes the project root") from exc
    return candidate


def iter_files(project_root: str):
    root = resolve_project_root(project_root)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        yield path


def load_project_instructions(project_root: str, max_chars: int = 30000) -> str:
    root = resolve_project_root(project_root)
    chunks: list[str] = []
    remaining = max_chars

    for filename in INSTRUCTION_FILES:
        path = root / filename
        if not path.is_file() or remaining <= 0:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        text = text[:remaining]
        chunks.append(f"===== {filename} =====\n{text}")
        remaining -= len(text)

    return "\n\n".join(chunks)


def capture_text_snapshot(project_root: str, max_total_chars: int = 1_500_000) -> dict[str, str]:
    root = resolve_project_root(project_root)
    snapshot: dict[str, str] = {}
    total = 0

    preferred_suffixes = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
        ".toml", ".ini", ".cfg", ".md", ".txt", ".html", ".css",
    }

    for path in sorted(iter_files(project_root)):
        if path.suffix.lower() not in preferred_suffixes:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        if len(text) > 200_000:
            continue
        if total + len(text) > max_total_chars:
            break

        snapshot[str(path.relative_to(root))] = text
        total += len(text)

    return snapshot
