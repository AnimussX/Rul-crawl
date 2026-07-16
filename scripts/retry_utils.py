# scripts/retry_utils.py

import time
from typing import Optional


def wait_with_stop_check(seconds: float, stop_event=None) -> bool:
    """
    Ждёт `seconds` секунд, проверяя stop_event каждую секунду.
    Возвращает True, если дождались полностью.
    Возвращает False, если был запрошен преждевременный стоп.
    """
    elapsed = 0
    while elapsed < seconds:
        if stop_event and stop_event.is_set():
            return False
        time.sleep(1)
        elapsed += 1
    return True