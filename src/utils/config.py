import json
from pathlib import Path

CONFIG_FILE = Path(Path().absolute(), '.preptura_config.json')

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

if __name__ == "__main__":
    print(f"CONFIG_FILE: {CONFIG_FILE}")
    config = load_config()
    print("Current configuration:", config)
    
    # Example of modifying and saving the config
    config['example_key'] = 'example_value'
    save_config(config)
    print("Updated configuration saved.")
    
    # Reload to verify
    config = load_config()
    print("Reloaded configuration:", config)

    # Clean up the config file
    del config['example_key']
    print("Removed example_key from configuration.")