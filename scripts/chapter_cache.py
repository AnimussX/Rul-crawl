# scripts/chapter_cache.py

import json
import sqlite3
from pathlib import Path
from typing import Dict, Optional, Any, List

from scripts.settings import load_settings


class ChapterCache:
    """Абстракция над кэшем глав: JSON-файлы или SQLite."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.settings = load_settings()
        self.cache_type = self.settings.get("cache_type", "json")
        if self.cache_type == "sqlite":
            self._init_sqlite()

    def _init_sqlite(self):
        db_path = self.data_dir / "cache.db"
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY,
                chapter_idx INTEGER NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                body TEXT NOT NULL,
                images_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chapter_idx)
            )
        """)
        self.conn.commit()

    def get_chapter_file_path(self, idx: int) -> Path:
        return self.data_dir / "chapters_json" / f"{idx:05d}.json"

    def save_chapter(self, idx: int, title: str, url: str, body: str, images: Dict[str, str]):
        if self.cache_type == "json":
            json_file = self.get_chapter_file_path(idx)
            json_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "id": idx,
                "title": title,
                "url": url,
                "body": body,
                "images": images,
            }
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            images_json = json.dumps(images)
            self.conn.execute("""
                INSERT OR REPLACE INTO chapters (chapter_idx, title, url, body, images_json)
                VALUES (?, ?, ?, ?, ?)
            """, (idx, title, url, body, images_json))
            self.conn.commit()

    def load_chapter(self, idx: int) -> Optional[Dict[str, Any]]:
        if self.cache_type == "json":
            json_file = self.get_chapter_file_path(idx)
            if json_file.exists():
                with open(json_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        else:
            cursor = self.conn.execute("""
                SELECT title, url, body, images_json FROM chapters WHERE chapter_idx = ?
            """, (idx,))
            row = cursor.fetchone()
            if row:
                return {
                    "title": row[0],
                    "url": row[1],
                    "body": row[2],
                    "images": json.loads(row[3])
                }
            return None

    def delete_chapter(self, idx: int):
        if self.cache_type == "json":
            json_file = self.get_chapter_file_path(idx)
            if json_file.exists():
                json_file.unlink()
        else:
            self.conn.execute("DELETE FROM chapters WHERE chapter_idx = ?", (idx,))
            self.conn.commit()

    def clear_cache(self):
        if self.cache_type == "json":
            chapters_dir = self.data_dir / "chapters_json"
            if chapters_dir.exists():
                import shutil
                shutil.rmtree(chapters_dir)
        else:
            self.conn.execute("DELETE FROM chapters")
            self.conn.commit()

    def migrate_from_json(self):
        if self.cache_type != "sqlite":
            return
        json_dir = self.data_dir / "chapters_json"
        if not json_dir.is_dir():
            return
        for json_file in json_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.save_chapter(
                    idx=data["id"],
                    title=data["title"],
                    url=data["url"],
                    body=data["body"],
                    images=data["images"]
                )
            except Exception:
                continue

    def close(self):
        if self.cache_type == "sqlite":
            self.conn.close()

    # --- Новые методы для кэширования списка глав ---
    def save_chapters_list(self, chapters: List[Dict]):
        """Сохраняет список глав (id и title) в JSON."""
        cache_file = self.data_dir / "chapters_cache.json"
        data = [{"id": ch["id"], "title": ch["title"]} for ch in chapters]
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_chapters_list(self) -> Optional[List[Dict]]:
        cache_file = self.data_dir / "chapters_cache.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None