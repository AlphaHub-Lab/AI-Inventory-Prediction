import os
import sys
import time
import subprocess
import signal
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

# Find python executable in .venv if present
if sys.platform == "win32":
    VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
    NPM_CMD = "npm.cmd"
else:
    VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
    NPM_CMD = "npm"

PYTHON_EXE = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

def check_backend_health():
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/health", headers={"User-Agent": "HealthCheck"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False

def check_frontend_health():
    try:
        req = urllib.request.Request("http://localhost:5173", headers={"User-Agent": "HealthCheck"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False

def check_db_connection():
    try:
        env_file = ROOT / ".env"
        db_url = None
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("DATABASE_URL="):
                    db_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        if not db_url:
            return False

        from sqlalchemy import create_engine, text
        engine = create_engine(db_url, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        print(f"    [!] Database check notice: {exc}")
        return False

def ensure_postgres():
    print("[*] Checking database connectivity...")
    if check_db_connection():
        print("    [OK] Connected to configured PostgreSQL database.")
        return

    print("[*] Database not directly reachable. Attempting to start with Docker Compose...")
    try:
        subprocess.run(["docker", "compose", "up", "-d", "--wait", "db"], cwd=str(ROOT), check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("PostgreSQL could not be reached and Docker is unavailable. Please check your DATABASE_URL in .env or start Docker Desktop.") from exc

def main():
    print("=" * 60)
    print("       Stockwise AI — Unified Project Launcher")
    print("=" * 60)

    try:
        ensure_postgres()
    except RuntimeError as exc:
        print(f"[!] {exc}")
        sys.exit(1)

    processes = []

    def cleanup(signum=None, frame=None):
        print("\n[*] Shutting down servers gracefully...")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        print("[+] All services stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("[*] Starting FastAPI Backend on http://127.0.0.1:8000 ...")
    backend_proc = subprocess.Popen(
        [PYTHON_EXE, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(BACKEND_DIR)
    )
    processes.append(backend_proc)

    print("[*] Starting Vite Frontend on http://localhost:5173 ...")
    frontend_proc = subprocess.Popen(
        [NPM_CMD, "run", "dev"],
        cwd=str(FRONTEND_DIR),
        shell=(sys.platform == "win32")
    )
    processes.append(frontend_proc)

    print("[*] Waiting for services to be healthy...")
    backend_ready = False
    frontend_ready = False

    for _ in range(30):
        if not backend_ready and check_backend_health():
            backend_ready = True
            print("    [OK] Backend is ready at http://127.0.0.1:8000")
        if not frontend_ready and check_frontend_health():
            frontend_ready = True
            print("    [OK] Frontend is ready at http://localhost:5173")
        if backend_ready and frontend_ready:
            break
        time.sleep(1)

    print("\n" + "=" * 60)
    print(" [READY] Both services are running successfully!")
    print("=" * 60)
    print(" Web Dashboard:   http://localhost:5173")
    print(" API Docs:        http://127.0.0.1:8000/docs")
    print("\n Demo Login Credentials:")
    print("   Admin:    admin@inventory.example.com    / Admin123!")
    print("   Manager:  manager@inventory.example.com  / Manager123!")
    print("   Staff:    staff@inventory.example.com    / Staff123!")
    print("=" * 60)
    print(" Press Ctrl+C at any time to stop both servers.\n")

    try:
        webbrowser.open("http://localhost:5173")
    except Exception:
        pass

    try:
        while True:
            time.sleep(1)
            # Check if any process terminated unexpectedly
            for p in processes:
                if p.poll() is not None:
                    print(f"[!] Process {p.args} stopped unexpectedly.")
                    cleanup()
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
