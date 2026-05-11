# kivy_app/utils/import_data.py
import os
import shutil
import sqlite3
from kivy_app.utils.paths import get_novels_base, get_db_path, get_novels_output_dir

def import_termux_data(source_novelsbase: str, source_db: str, progress_callback=None):
    """
    Копирует Novelsbase и базу данных из Termux в песочницу приложения.
    Обновляет пути в базе данных на новые (внутренние).
    source_novelsbase: путь к папке Novelsbase в Termux (например, /storage/emulated/0/lncrawl/Novelsbase)
    source_db: путь к файлу Novels.db в Termux (например, /storage/emulated/0/lncrawl/Novelsbase/Novels.db)
    progress_callback: функция, принимающая строку для отображения статуса.
    """
    def log(msg):
        if progress_callback:
            progress_callback(msg)

    target_novelsbase = get_novels_base()
    target_db = get_db_path()
    target_novels_output = get_novels_output_dir()

    # Создаём целевые папки
    os.makedirs(target_novelsbase, exist_ok=True)
    os.makedirs(target_novels_output, exist_ok=True)

    # 1. Копируем папку Novelsbase (рекурсивно)
    if os.path.isdir(source_novelsbase):
        log(f"Копирование Novelsbase из {source_novelsbase} ...")
        for item in os.listdir(source_novelsbase):
            s = os.path.join(source_novelsbase, item)
            d = os.path.join(target_novelsbase, item)
            if os.path.isdir(s):
                if not os.path.exists(d):
                    shutil.copytree(s, d)
            else:
                if not os.path.exists(d):
                    shutil.copy2(s, d)
        log("Novelsbase скопирована.")
    else:
        log("Исходная папка Novelsbase не найдена.")

    # 2. Копируем базу данных (если ещё не скопирована вместе с папкой)
    db_filename = os.path.basename(source_db) if source_db else 'Novels.db'
    if source_db and os.path.isfile(source_db):
        target_db_path = os.path.join(target_novelsbase, db_filename) if db_filename == 'Novels.db' else target_db
        # Если база уже лежит в Novelsbase, она уже скопирована, но проверим
        if not os.path.exists(target_db_path):
            shutil.copy2(source_db, target_db_path)
        # Используем скопированную базу для дальнейших операций
        working_db = target_db_path
        log("База данных скопирована.")
    else:
        log("Исходный файл БД не указан или не найден.")
        return

    # 3. Обновляем пути в базе данных
    try:
        conn = sqlite3.connect(working_db)
        c = conn.cursor()
        # Получаем все записи
        c.execute("SELECT id, target_dir, output_books FROM novels")
        rows = c.fetchall()
        for novel_id, old_target, old_output in rows:
            # Заменяем корневую часть пути
            new_target = old_target.replace(
                os.path.dirname(source_novelsbase) or '/storage/emulated/0/lncrawl',
                os.path.dirname(target_novelsbase)
            )
            new_output = old_output.replace(
                os.path.dirname(source_novelsbase) or '/storage/emulated/0/lncrawl',
                target_novels_output
            )
            # Обновление
            c.execute("UPDATE novels SET target_dir=?, output_books=? WHERE id=?",
                      (new_target, new_output, novel_id))
        conn.commit()
        conn.close()
        log("Пути в базе данных обновлены.")
    except Exception as e:
        log(f"Ошибка при обновлении БД: {e}")