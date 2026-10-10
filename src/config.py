import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR, OUT_DIR = ROOT / "data", ROOT / "outputs"
DATA_DIR.mkdir(exist_ok=True); OUT_DIR.mkdir(exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DORMANT_DAYS = int(os.getenv("DORMANT_DAYS", 90))
CLIENT_NAME = os.getenv("CLIENT_NAME", "Client fictif")


AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
PRIV_DEPTS = {x.strip() for x in os.getenv("PRIV_DEPTS", "IT,Sécurité,Security,Information Technology").split(",")}
