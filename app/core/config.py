import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

print("DEBUG KEY:", OPENROUTER_API_KEY)