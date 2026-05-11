import json
from pathlib import Path

METADATA_FILE = "metadata.json"

def save_metadata(data_dir, title, author, cover_url, synopsis, chapters):
    metadata = {
        'title': title,
        'author': author,
        'cover_url': cover_url,
        'synopsis': synopsis,
        'chapters': chapters
    }
    with open(data_dir / METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

def load_metadata(data_dir):
    meta_path = data_dir / METADATA_FILE
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None