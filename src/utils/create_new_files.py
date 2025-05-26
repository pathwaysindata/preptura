# Re-run after state reset: create module files again
from pathlib import Path
import pandas as pd
base_dir = Path("/home/shanks/data/github/preptura/src")
from pathlib import Path

# Set up new config and manager scaffolding
base_dir = Path("/mnt/data/preptura_refactor/src")
utils_dir = base_dir / "utils"
utils_dir.mkdir(parents=True, exist_ok=True)

# config.py - for loading/saving configuration like default folder
config_code = """
import json
from pathlib import Path

CONFIG_FILE = Path.home() / '.preptura_config.json'

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
"""

# file_manager.py - for scanning files in a folder
file_manager_code = """
from pathlib import Path

def list_supported_files(folder_path, extensions=('.csv', '.xlsx')):
    folder = Path(folder_path)
    return sorted([f for f in folder.glob('*') if f.suffix.lower() in extensions])
"""

(utils_dir / "config.py").write_text(config_code.strip())
(utils_dir / "file_manager.py").write_text(file_manager_code.strip())

