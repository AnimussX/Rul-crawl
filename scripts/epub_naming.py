# scripts/epub_naming.py

import re
from pathlib import Path
from gui.database import STATUS_COMPLETED, STATUS_DROPPED_BY_AUTHOR, STATUS_DROPPED_BY_TRANSLATOR


def _sanitize(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip() or "novel"


def build_final_epub_name(out_path: Path, status: str, title: str, loaded: list, last_read_chapter: int) -> str:
    safe_title = _sanitize(title)

    if status == STATUS_COMPLETED:
        return f"{safe_title}.epub"

    if status in (STATUS_DROPPED_BY_AUTHOR, STATUS_DROPPED_BY_TRANSLATOR):
        if loaded:
            first_idx = loaded[0][0]
            last_title = _sanitize(loaded[-1][1])
            base_name = f"{safe_title} - {first_idx} - {last_title}"
        else:
            base_name = safe_title
        suffix = f" (до {last_read_chapter} главы)" if last_read_chapter > 0 else ""
        return f"{base_name}{suffix}.epub"

    if last_read_chapter > 0:
        return f"{out_path.stem} (до {last_read_chapter} главы){out_path.suffix}"
    return out_path.name