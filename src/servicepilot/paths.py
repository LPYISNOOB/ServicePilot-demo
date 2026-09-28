import os
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path(os.getenv("SERVICEPILOT_PROJECT_DIR", str(PACKAGE_DIR.parent.parent))).resolve()
DATA_DIR = PROJECT_DIR / "data"
POLICY_DIR = DATA_DIR / "policies"
DEFAULT_DB_PATH = DATA_DIR / "servicepilot.db"
DEFAULT_CHECKPOINT_PATH = DATA_DIR / "checkpoints.db"
EVAL_DIR = PROJECT_DIR / "evals"
REPORT_DIR = PROJECT_DIR / "reports"
CONFIG_DIR = PROJECT_DIR / "config"
FRONTEND_DIR = PROJECT_DIR / "frontend"
