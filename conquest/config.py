"""Paths and starting settings.

Everything personal (home, drive limits, interests) is stored in the database
and edited in the Settings tab. The values here only seed a brand-new database.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=value lines from .env without overriding the real environment."""
    env_file = path or PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return

    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()

DATA_DIR = Path(os.environ.get("CONQUEST_DATA_DIR", PROJECT_ROOT / "data"))
DB_PATH = Path(os.environ.get("CONQUEST_DB", DATA_DIR / "conquest.db"))
INBOX_DIR = DATA_DIR / "inbox"
IMPORTED_DIR = INBOX_DIR / "imported"

# Where drive times are measured from in a brand-new database. Set your own in
# .env (see .env.example) or change it later in the Settings tab.
DEFAULT_HOME_LABEL = os.environ.get("CONQUEST_HOME_LABEL", "Orlando, FL")
DEFAULT_HOME_LAT = float(os.environ.get("CONQUEST_HOME_LAT", "28.5384"))
DEFAULT_HOME_LNG = float(os.environ.get("CONQUEST_HOME_LNG", "-81.3789"))

DEFAULT_INTEREST_PROFILE = (
    "I like big comic and pop culture conventions, tech expos and gadget shows, maker faires, "
    "and anything space, science, math or engineering related, especially hands-on, interactive "
    "exhibits. Robotics showcases are great, and so are live orchestras playing a movie's score "
    "while the film plays. Interesting talks and lectures are a plus. "
    "(This is an example: rewrite it in Settings to describe what you're into.)"
)
