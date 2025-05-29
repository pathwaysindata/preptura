from pathlib import Path

def list_supported_files(folder_path, extensions=(".csv", ".xlsx")):
    folder = Path(folder_path)
    return sorted([f for f in folder.glob('*') if f.suffix.lower() in extensions])