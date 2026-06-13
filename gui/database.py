import sqlite3
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from scripts.paths import DB_PATH

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
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_novel(title: str, url: str, target_dir: str, output_books: str, synopsis: Optional[str] = None, total_chapters: int = 0, section: str = 'Разные') -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO novels (title, url, target_dir, output_books, synopsis, total_chapters, section)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (title, url, target_dir, output_books, synopsis, total_chapters, section))
    novel_id = c.lastrowid
    conn.commit()
    conn.close()
    return novel_id

def get_novel(novel_id: int) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT id, title, url, synopsis, target_dir, output_books, total_chapters, section, date_added
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
            'date_added': row[8]
        }
    return None

def get_all_novels() -> List[Tuple[int, str, str, int]]:
    """Возвращает список кортежей (id, title, section, total_chapters)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, title, section, total_chapters FROM novels ORDER BY title COLLATE NOCASE')
    rows = c.fetchall()
    conn.close()
    return rows

def update_novel(novel_id: int, **kwargs):
    """Обновляет поля записи. Допустимые ключи: title, synopsis, target_dir, output_books, total_chapters, section."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    values = []
    allowed_fields = ('title', 'synopsis', 'target_dir', 'output_books', 'total_chapters', 'section')
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

def delete_novel(novel_id: int, delete_files: bool = False) -> bool:
    """Удаляет запись о новелле из БД. Если delete_files=True, также удаляет связанные папки."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Сначала получим информацию о путях
    c.execute("SELECT target_dir, output_books FROM novels WHERE id = ?", (novel_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    target_dir, output_books = row

    # Удаляем запись
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
    
def get_all_novels(section=None):
    """Возвращает список кортежей (id, title, section, total_chapters).
    Если section указан и не равен "Все", фильтрует по разделу."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if section is None or section == "Все":
        c.execute('SELECT id, title, section, total_chapters FROM novels ORDER BY title COLLATE NOCASE')
    else:
        c.execute('SELECT id, title, section, total_chapters FROM novels WHERE section = ? ORDER BY title COLLATE NOCASE', (section,))
    rows = c.fetchall()
    conn.close()
    return rows