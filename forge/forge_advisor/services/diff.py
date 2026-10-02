import difflib
import subprocess
from pathlib import Path

from forge_advisor.services.project import resolve_project_root


def get_workspace_diff(project_root: str, baseline: dict[str, str]) -> str:
    root = resolve_project_root(project_root)

    # Prefer the real git diff when the repository is already under git.
    git_dir = root / ".git"
    if git_dir.exists():
        try:
            result = subprocess.run(
                ["git", "diff", "--no-ext-diff", "--unified=5", "--"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Fallback for a non-git demo repository: compare against the pre-run snapshot.
    chunks: list[str] = []
    current_paths = set()
    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.parts and ".forge" not in path.parts:
            try:
                rel = str(path.relative_to(root))
                current_paths.add(rel)
                new = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            old = baseline.get(rel)
            if old != new:
                chunks.append(
                    "".join(
                        difflib.unified_diff(
                            (old or "").splitlines(True),
                            new.splitlines(True),
                            fromfile=f"a/{rel}",
                            tofile=f"b/{rel}",
                        )
                    )
                )

    for rel, old in baseline.items():
        if rel not in current_paths:
            chunks.append(
                "".join(
                    difflib.unified_diff(
                        old.splitlines(True),
                        [],
                        fromfile=f"a/{rel}",
                        tofile=f"b/{rel}",
                    )
                )
            )

    return "\n".join(chunk for chunk in chunks if chunk) or "No textual changes detected."
