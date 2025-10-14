import os
from pathlib import Path

_CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = _CURRENT_FILE.parent

if env_root := os.getenv("PROJECT_ROOT"):
    PROJECT_ROOT = Path(env_root).resolve()

CUSTOM_PARSERS_DIR = PROJECT_ROOT / "custom_parsers"
TESTS_DIR = PROJECT_ROOT / "tests"
CUSTOM_PARSERS_TESTS_DIR = TESTS_DIR / "custom_parsers"
LOG_SAMPLES_DIR = PROJECT_ROOT / "log_samples"
EXAMPLES_DIR = PROJECT_ROOT / "examples"

ALLOWED_READ_DIRS = [
    str(PROJECT_ROOT),
]

ALLOWED_WRITE_DIRS = [
    str(CUSTOM_PARSERS_DIR),
    str(CUSTOM_PARSERS_TESTS_DIR),
]

ALLOWED_SEARCH_DIRS = [
    str(PROJECT_ROOT),
    str(LOG_SAMPLES_DIR),
    str(EXAMPLES_DIR),
]

CUSTOM_PARSERS_DIR.mkdir(exist_ok=True)
CUSTOM_PARSERS_TESTS_DIR.mkdir(parents=True, exist_ok=True)

