import os
import pathlib
import subprocess
import venv

ROOT = pathlib.Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
PYTHON = VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv() -> None:
    if not VENV_DIR.exists():
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    subprocess.check_call(
        [str(PYTHON), "-m", "pip", "install", "-r", "requirements.txt"]
    )


def main() -> None:
    ensure_venv()
    env = os.environ.copy()
    subprocess.check_call([str(PYTHON), "asr_server.py"], env=env)


if __name__ == "__main__":
    main()
