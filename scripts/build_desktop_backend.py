"""Build the local FastAPI service bundled in platform desktop installers."""

from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DIST = BACKEND / "dist"
WORK = BACKEND / "build" / "pyinstaller"


def main() -> None:
    executable = "stockwise-backend.exe" if os.name == "nt" else "stockwise-backend"
    target = DIST / "stockwise-backend" / executable
    if DIST.exists():
        shutil.rmtree(DIST)
    if WORK.exists():
        shutil.rmtree(WORK)

    separator = ";" if os.name == "nt" else ":"
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--name", "stockwise-backend", "--distpath", str(DIST), "--workpath", str(WORK), "--specpath", str(WORK),
        "--paths", str(BACKEND),
        "--hidden-import", "app.main", "--collect-all", "uvicorn", "--collect-all", "fastapi", "--collect-all", "sqlalchemy",
        "--collect-all", "pydantic_settings", "--collect-all", "jose",
        "--collect-all", "passlib", "--collect-all", "slowapi", "--collect-all", "psycopg",
        "--hidden-import", "pandas", "--hidden-import", "numpy", "--hidden-import", "joblib",
        "--hidden-import", "sklearn.metrics",
        "--hidden-import", "xgboost", "--hidden-import", "xgboost.core", "--hidden-import", "xgboost.sklearn",
        "--collect-binaries", "xgboost", "--collect-data", "xgboost",
        "--hidden-import", "openpyxl", "--hidden-import", "pypdf", "--hidden-import", "PIL",
        "--exclude-module", "torch", "--exclude-module", "torchvision", "--exclude-module", "torchaudio",
        "--exclude-module", "matplotlib", "--exclude-module", "pytest", "--exclude-module", "hypothesis",
        "--exclude-module", "dask", "--exclude-module", "numba",
        "--add-data", f"{BACKEND / 'migrations'}{separator}backend/migrations",
        "--add-data", f"{BACKEND / 'alembic.ini'}{separator}backend",
        "--add-data", f"{ROOT / 'ml'}{separator}ml",
        str(BACKEND / "desktop_server.py"),
    ]
    subprocess.run(args, cwd=ROOT, check=True)
    if not target.is_file():
        raise SystemExit(f"PyInstaller completed but the backend executable was not created: {target}")
    print(f"Built backend: {target}")


if __name__ == "__main__":
    main()
