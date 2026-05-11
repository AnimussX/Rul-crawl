import subprocess
import threading
import time
import tempfile
import os
import sys
from typing import Optional, Callable

def run_main_with_log(
    url: str,
    chapters_spec: str,
    login: str,
    password: str,
    total_chapters: Optional[int] = None,
    workers: int = 2,
    proxy_file: Optional[str] = None,
    debug: bool = False,
    target_dir: Optional[str] = None,
    force: bool = False,
    ignore_image_errors: bool = False,
    ignore_errors: bool = False,  # новый параметр
    log_callback: Optional[Callable[[str], None]] = None
) -> bool:
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.log', delete=False) as tmp:
        log_file = tmp.name

    cmd = [
        sys.executable, "main.py",
        url,
        "--chapters", chapters_spec,
        "--login", login,
        "--password", password,
        "--workers", str(workers),
        "--log-file", log_file,
    ]
    if total_chapters:
        cmd.extend(["--progress-total", str(total_chapters)])
    if proxy_file:
        cmd.extend(["--proxy-file", proxy_file])
    if debug:
        cmd.append("--debug")
    if target_dir:
        cmd.extend(["--target-dir", target_dir])
    if force:
        cmd.append("--force")
    if ignore_image_errors:
        cmd.append("--ignore-image-errors")
    if ignore_errors:
        cmd.append("--ignore-errors")

    if log_callback:
        log_callback(f"🚀 Запуск: {' '.join(cmd)}")

    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def reader():
        try:
            with open(log_file, 'r') as f:
                while process.poll() is None:
                    line = f.readline()
                    if line:
                        if log_callback:
                            log_callback(line.rstrip())
                    else:
                        time.sleep(0.1)
                for line in f:
                    if log_callback:
                        log_callback(line.rstrip())
        except Exception as e:
            if log_callback:
                log_callback(f"Ошибка чтения лога: {e}")
        finally:
            try:
                os.remove(log_file)
            except:
                pass

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    process.wait()
    thread.join(timeout=1)
    return process.returncode == 0