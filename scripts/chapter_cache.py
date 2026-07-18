# scripts/chapter_cache.py

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Optional, Any, List
import threading

from scripts.settings import load_settings


class ChapterCache:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.settings = load_settings()
        self.cache_type = self.settings.get("cache_type", "json")
        self._lock = threading.Lock()
        if self.cache_type == "sqlite":
            self._init_sqlite()

    def _init_sqlite(self):
        db_path = self.data_dir / "cache.db"
        self.conn = sqlite3.connect(str(db_path), timeout=20.0, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous = OFF")
        self.conn.execute("PRAGMA cache_size = 10000")
        self.conn.execute("PRAGMA temp_store = MEMORY")   # добавлено — временные данные в память, не на диск
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY,
                chapter_idx INTEGER NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                body TEXT NOT NULL,
                images_json TEXT NOT NULL,
                status INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chapter_idx)
            )
        """)
        cursor = self.conn.execute("PRAGMA table_info(chapters)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'status' not in columns:
            self.conn.execute("ALTER TABLE chapters ADD COLUMN status INTEGER DEFAULT 0")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_chapter_idx ON chapters(chapter_idx)")
        self.conn.commit()

    def get_chapter_file_path(self, idx: int) -> Path:
        return self.data_dir / "chapters_json" / f"{idx:05d}.json"

    def save_chapter(self, idx: int, title: str, url: str, body: str, images: Dict[str, str], status: int = 0):
        if self.cache_type == "json":
            json_file = self.get_chapter_file_path(idx)
            json_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "id": idx,
                "title": title,
                "url": url,
                "body": body,
                "images": images,
                "status": status,
            }
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            images_json = json.dumps(images)
            with self._lock:
                self.conn.execute("""
                    INSERT OR REPLACE INTO chapters (chapter_idx, title, url, body, images_json, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (idx, title, url, body, images_json, status))

    def commit(self):
        if self.cache_type == "sqlite":
            self.conn.commit()

    def rollback(self):
        if self.cache_type == "sqlite":
            self.conn.rollback()

    def commit_chapters(self, indices: List[int]):
        if self.cache_type != "sqlite":
            return
        if not indices:
            return
        placeholders = ','.join('?' * len(indices))
        max_retries = 5
        for attempt in range(max_retries):
            try:
                self.conn.execute(
                    f"UPDATE chapters SET status = 1 WHERE chapter_idx IN ({placeholders})",
                    indices
                )
                self.conn.commit()
                return
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise

    def clear_drafts(self):
        if self.cache_type != "sqlite":
            return
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.conn.execute("DELETE FROM chapters WHERE status = 0")
                self.conn.commit()
                return
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    raise

    def load_chapter(self, idx: int) -> Optional[Dict[str, Any]]:
        if self.cache_type == "json":
            json_file = self.get_chapter_file_path(idx)
            if json_file.exists():
                with open(json_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        else:
            with self._lock:
                cursor = self.conn.execute(
                    "SELECT title, url, body, images_json FROM chapters WHERE chapter_idx = ? AND status = 1",
                    (idx,)
                )
                row = cursor.fetchone()
            if row:
                return {"title": row[0], "url": row[1], "body": row[2], "images": json.loads(row[3])}
            return None

    def get_chapter_status(self, idx: int) -> Optional[int]:
        if self.cache_type == "json":
            json_file = self.get_chapter_file_path(idx)
            if json_file.exists():
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("status", 1)
            return None
        else:
            cursor = self.conn.execute("SELECT status FROM chapters WHERE chapter_idx = ?", (idx,))
            row = cursor.fetchone()
            return row[0] if row else None

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
                    images=data["images"],
                    status=data.get("status", 1)
                )
            except Exception:
                continue
        self.commit()

    def close(self):
        if self.cache_type == "sqlite":
            self.conn.close()

    # Статические методы для миграции старых chapters_cache.json в metadata.json
    @staticmethod
    def migrate_old_chapters_cache(data_dir: Path):
        """Если существует устаревший chapters_cache.json, переносим его данные в metadata.json (если нет метаданных) и удаляем."""
        old_cache = data_dir / "chapters_cache.json"
        if not old_cache.exists():
            return

        meta_file = data_dir / "metadata.json"
        # Переносим только если метаданных ещё нет (чтобы не перезаписать)
        if not meta_file.exists():
            try:
                with open(old_cache, "r", encoding="utf-8") as f:
                    old_chapters = json.load(f)
                # Создаём минимальные метаданные с главами
                metadata = {
                    "title": "",
                    "author": "",
                    "cover_url": "",
                    "synopsis": "",
                    "chapters": old_chapters
                }
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                print(f"✅ Перенесены данные из {old_cache} в metadata.json")
            except Exception as e:
                print(f"⚠️ Ошибка миграции chapters_cache.json: {e}")
        # В любом случае удаляем устаревший файл
        try:
            old_cache.unlink()
        except Exception:
            pass