# scripts/ranobes_worker.py
"""
Изолированная точка входа для получения информации о новелле через
SeleniumBase (ranobes.com). Вынесена в отдельный модуль верхнего уровня —
это обязательное условие для multiprocessing со start method 'spawn':
дочерний процесс не наследует sys.path/состояние родителя (в отличие от
fork), а fork() многопоточного Textual-приложения приводит к тихим
дедлокам на унаследованных локах (subprocess, filelock, malloc).
"""

import os
import sys
from pathlib import Path

# Критично для spawn: гарантируем доступность gui.*/scripts.* модулей
# до того, как что-либо ещё попытается их импортировать.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import io
import logging


class _QueueLogStream(io.StringIO):
    """Перехватывает print()/stdout,stderr и шлёт строки в очередь логов."""

    def __init__(self, log_q):
        super().__init__()
        self._log_q = log_q

    def write(self, s):
        if s.strip():
            self._log_q.put(s.strip())
        return len(s)

    def flush(self):
        pass


class _QueueLogHandler(logging.Handler):
    """Перенаправляет записи logging-модуля (selenium, seleniumbase,
    pyvirtualdisplay, scripts.ranobes, scripts.selenium_termux_config)
    в ту же очередь, что и print()."""

    def __init__(self, log_q):
        super().__init__()
        self._log_q = log_q

    def emit(self, record):
        try:
            self._log_q.put(f"[{record.name}] {self.format(record)}")
        except Exception:
            pass


def ranobes_info_worker(url, login, password, result_q, log_q):
    """Точка входа для дочернего процесса (запускается через spawn)."""
    if sys.platform == 'android':
        sys.platform = 'linux'

    # Патч os.link не наследуется гарантированно при spawn (в отличие от
    # fork), поэтому применяем его заново внутри самого дочернего процесса.
    if not hasattr(os, 'link'):
        def _dummy_link(src, dst, *a, **kw):
            raise OSError("Hard links are not supported on Android")
        os.link = _dummy_link
        os.supports_dir_fd.add(_dummy_link)

    os.environ['FILELOCK_USE_FLOCK'] = '0'
    import filelock
    filelock.FileLock = filelock.SoftFileLock

    log_stream = _QueueLogStream(log_q)
    sys.stdout = log_stream
    sys.stderr = log_stream

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(_QueueLogHandler(log_q))

    def emit_log(msg):
        log_q.put(msg)

    emit_log("🔧 Процесс стартовал (spawn), хаки применены")
    try:
        emit_log("📡 Вызов get_novel_info...")
        from gui.crawler_utils import get_novel_info
        title, synopsis, chapters = get_novel_info(url, login, password)
        emit_log(f"✅ get_novel_info вернула title='{title}', глав={len(chapters) if chapters else 0}")
        result_q.put({"success": True, "title": title, "synopsis": synopsis, "chapters": chapters})
    except Exception as e:
        import traceback
        emit_log(f"❌ Исключение в get_novel_info: {e}")
        emit_log(traceback.format_exc())
        result_q.put({"success": False, "error": str(e)})
    finally:
        emit_log("🏁 Процесс завершает работу")
        log_q.put(None)