# gui/database.py

import sqlite3
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from scripts.paths import DB_PATH

STATUS_IN_PROGRESS = "в работе"
STATUS_DROPPED_BY_TRANSLATOR = "заброшено переводчиком"
STATUS_DROPPED_BY_AUTHOR = "заброшено автором"
STATUS_COMPLETED = "завершено"
STATUSES = [STATUS_IN_PROGRESS, STATUS_DROPPED_BY_TRANSLATOR, STATUS_DROPPED_BY_AUTHOR, STATUS_COMPLETED]

DEFAULT_SOURCE = "rulate"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS novels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            synopsis TEXT,
            target_dir TEXT NOT NULL,
            output_books TEXT NOT NULL,
            total_chapters INTEGER NOT NULL DEFAULT 0,
            section TEXT DEFAULT 'Разные',
            status TEXT DEFAULT 'в работе',
            last_read_chapter INTEGER DEFAULT 0,
            source TEXT DEFAULT 'rulate',
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def migrate_db():
    """Добавляет новые колонки, если их нет."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(novels)")
    columns = [col[1] for col in c.fetchall()]
    if 'status' not in columns:
        c.execute("ALTER TABLE novels ADD COLUMN status TEXT DEFAULT 'в работе'")
    if 'last_read_chapter' not in columns:
        c.execute("ALTER TABLE novels ADD COLUMN last_read_chapter INTEGER DEFAULT 0")
    if 'source' not in columns:
        c.execute(f"ALTER TABLE novels ADD COLUMN source TEXT DEFAULT '{DEFAULT_SOURCE}'")
    conn.commit()
    conn.close()


def add_novel(title: str, url: str, target_dir: str, output_books: str,
              synopsis: Optional[str] = None, total_chapters: int = 0,
              section: str = 'Разные', status: str = STATUS_IN_PROGRESS,
              last_read_chapter: int = 0, source: str = DEFAULT_SOURCE) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO novels (title, url, target_dir, output_books, synopsis, total_chapters, section, status, last_read_chapter, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, url, target_dir, output_books, synopsis, total_chapters, section, status, last_read_chapter, source))
    novel_id = c.lastrowid
    conn.commit()
    conn.close()
    return novel_id


def get_novel(novel_id: int) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT id, title, url, synopsis, target_dir, output_books, total_chapters, section, status, last_read_chapter, source, date_added
        FROM novels WHERE id = ?
    ''', (novel_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'title': row[1],
            'url': row[2],
            'synopsis': row[3],
            'target_dir': row[4],
            'output_books': row[5],
            'total_chapters': row[6],
            'section': row[7],
            'status': row[8],
            'last_read_chapter': row[9],
            'source': row[10] or DEFAULT_SOURCE,
            'date_added': row[11]
        }
    return None


def get_novel_by_target_dir(target_dir: str) -> Optional[Dict[str, Any]]:
    """Возвращает информацию о новелле по пути target_dir."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT id, title, url, synopsis, target_dir, output_books, total_chapters, section, status, last_read_chapter, source, date_added
        FROM novels WHERE target_dir = ?
    ''', (target_dir,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'title': row[1],
            'url': row[2],
            'synopsis': row[3],
            'target_dir': row[4],
            'output_books': row[5],
            'total_chapters': row[6],
            'section': row[7],
            'status': row[8],
            'last_read_chapter': row[9],
            'source': row[10] or DEFAULT_SOURCE,
            'date_added': row[11]
        }
    return None


def update_novel(novel_id: int, **kwargs):
    """Обновляет поля записи. Допустимые ключи: title, synopsis, target_dir, output_books,
    total_chapters, section, status, last_read_chapter, source."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    values = []
    allowed_fields = (
        'title', 'synopsis', 'target_dir', 'output_books', 'total_chapters',
        'section', 'status', 'last_read_chapter', 'source',
    )
    for key, value in kwargs.items():
        if key in allowed_fields:
            fields.append(f"{key} = ?")
            values.append(value)
    if fields:
        query = f"UPDATE novels SET {', '.join(fields)} WHERE id = ?"
        values.append(novel_id)
        c.execute(query, values)
        conn.commit()
    conn.close()


def get_all_novels(section=None, status=None, exclude_completed=False):
    """
    Возвращает список кортежей (id, title, section, total_chapters, status).
    - section: фильтр по разделу (если None или "Все" – все разделы)
    - status: если строка "Завершённые" – возвращает статусы 'завершено' и 'заброшено автором'.
              Если список/кортеж – фильтр по нескольким статусам.
              Если строка с конкретным статусом – фильтр по нему.
    - exclude_completed: если True, исключает статусы 'завершено' и 'заброшено автором'.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = "SELECT id, title, section, total_chapters, status FROM novels"
    conditions = []
    params = []

    if section and section != "Все":
        conditions.append("section = ?")
        params.append(section)

    # Обработка status
    if status == "Завершённые":
        # Подменяем на список из двух статусов
        status = (STATUS_COMPLETED, STATUS_DROPPED_BY_AUTHOR)
    if isinstance(status, (list, tuple)):
        if status:
            placeholders = ','.join('?' * len(status))
            conditions.append(f"status IN ({placeholders})")
            params.extend(status)
    elif status is not None:
        conditions.append("status = ?")
        params.append(status)
    elif exclude_completed:
        conditions.append(f"status NOT IN (?, ?)")
        params.extend([STATUS_COMPLETED, STATUS_DROPPED_BY_AUTHOR])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY title COLLATE NOCASE"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows


def get_completed_novels() -> List[Tuple[int, str]]:
    """Возвращает список (id, target_dir) для завершённых и заброшенных автором книг."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, target_dir FROM novels WHERE status IN (?, ?)",
              (STATUS_COMPLETED, STATUS_DROPPED_BY_AUTHOR))
    rows = c.fetchall()
    conn.close()
    return rows


def delete_novel(novel_id: int, delete_files: bool = False) -> bool:
    """Удаляет запись о новелле из БД. Если delete_files=True, также удаляет связанные папки."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT target_dir, output_books FROM novels WHERE id = ?", (novel_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    target_dir, output_books = row
    c.execute("DELETE FROM novels WHERE id = ?", (novel_id,))
    conn.commit()
    conn.close()
    if delete_files:
        if target_dir and Path(target_dir).exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        if output_books and Path(output_books).exists():
            try:
                Path(output_books).rmdir()
            except OSError:
                pass
    return True


def get_loaded_chapters_count(target_dir: str) -> int:
    """Возвращает количество загруженных глав (JSON-файлов) в папке chapters_json."""
    chapters_dir = Path(target_dir) / "chapters_json"
    if not chapters_dir.exists():
        return 0
    return len(list(chapters_dir.glob("*.json")))


# Инициализация и миграция при первом импорте
init_db()
migrate_db()
