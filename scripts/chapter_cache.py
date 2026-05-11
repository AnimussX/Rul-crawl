import json
from pathlib import Path

def get_chapter_file(chapters_dir, idx):
    return chapters_dir / f"{idx:05d}.json"

def save_chapter_json(chapter_file, chapter_data):
    chapter_file.parent.mkdir(parents=True, exist_ok=True)
    with open(chapter_file, 'w', encoding='utf-8') as f:
        json.dump(chapter_data, f, ensure_ascii=False, indent=2)

def load_chapter_json(chapter_file):
    if chapter_file.exists():
        with open(chapter_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def load_all_chapters(chapters_dir, start, end, force=False):
    loaded = []
    for i in range(start, end + 1):
        json_file = get_chapter_file(chapters_dir, i)
        chapter_data = load_chapter_json(json_file)
        if chapter_data and not force:
            loaded.append(chapter_data)
        else:
            loaded.append(None)
    return loaded