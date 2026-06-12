from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_conda_command() -> str:
    candidates = [
        Path("C:/Software/code_ide/miniconda/Scripts/conda.exe"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    conda_from_path = shutil.which("conda")
    if conda_from_path:
        return conda_from_path

    raise RuntimeError("Unable to find conda command. Please install conda or update script path.")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    conda_env_path = repo_root / ".conda"

    if not conda_env_path.exists():
        raise RuntimeError(f"Conda env not found at: {conda_env_path}")

    conda_cmd = _resolve_conda_command()
    pytest_args = sys.argv[1:] or ["-q"]

    cmd = [
        conda_cmd,
        "run",
        "-p",
        str(conda_env_path),
        "--no-capture-output",
        "python",
        "-m",
        "pytest",
        *pytest_args,
    ]

    completed = subprocess.run(cmd, cwd=repo_root, check=False)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
