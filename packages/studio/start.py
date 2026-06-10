"""HiveFlow Studio Startup Script"""
import subprocess
import sys
import os
import argparse

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT, "backend")
FRONTEND_DIR = os.path.join(ROOT, "frontend")


def start_backend():
    print("\n" + "=" * 40)
    print("  Starting Backend FastAPI (http://127.0.0.1:8000)")
    print("=" * 40 + "\n")

    python_exe = os.path.join(BACKEND_DIR, "venv", "Scripts", "python.exe")
    if sys.platform != "win32":
        python_exe = os.path.join(BACKEND_DIR, "venv", "bin", "python")

    return subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", "8000", "--reload"],
        cwd=BACKEND_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
    )


def start_frontend():
    print("\n" + "=" * 40)
    print("  Starting Frontend Vite (http://localhost:3000)")
    print("=" * 40 + "\n")

    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    return subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=FRONTEND_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
    )


def print_info():
    print()
    print("  HiveFlow Studio starting...")
    print("    Frontend:  http://localhost:3000")
    print("    Backend:   http://127.0.0.1:8000")
    print("    API Docs:  http://127.0.0.1:8000/docs")
    print()


def main():
    parser = argparse.ArgumentParser(description="HiveFlow Studio Launcher")
    parser.add_argument("--frontend-only", action="store_true", help="Start frontend only")
    parser.add_argument("--backend-only", action="store_true", help="Start backend only")
    args = parser.parse_args()

    start_all = not args.frontend_only and not args.backend_only
    procs = []

    try:
        if start_all or args.backend_only:
            procs.append(start_backend())

        if start_all or args.frontend_only:
            procs.append(start_frontend())

        print_info()

        if sys.platform == "win32":
            input("  Press Enter to stop all services...")
        else:
            try:
                for p in procs:
                    p.wait()
            except KeyboardInterrupt:
                pass
    finally:
        print("\n  Stopping services...")
        for p in procs:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("  Done.\n")


if __name__ == "__main__":
    main()