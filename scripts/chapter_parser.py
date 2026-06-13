# scripts/chapter_parser.py

from typing import List, Optional, Callable


def parse_chapters_spec(
    chapters_spec: str,
    total_chapters: int,
    log_func: Optional[Callable[[str], None]] = None
) -> List[int]:
    """
    Разбирает спецификацию глав, обрезает значения до доступного диапазона
    и выводит предупреждения через log_func, если передан.
    Возвращает отсортированный список номеров глав.
    """
    if not chapters_spec:
        return list(range(1, total_chapters + 1))

    selected = set()
    warnings = []

    for part in chapters_spec.split(','):
        part = part.strip()
        if not part:
            continue

        if '-' in part:
            try:
                s, e = map(int, part.split('-'))
            except ValueError:
                warnings.append(f"Неверный формат диапазона: {part}")
                continue
            s = max(1, min(s, total_chapters))
            e = max(1, min(e, total_chapters))
            if s <= e:
                selected.update(range(s, e + 1))
            else:
                warnings.append(f"Диапазон {part} не содержит доступных глав")
        else:
            try:
                ch = int(part)
            except ValueError:
                warnings.append(f"Неверный номер главы: {part}")
                continue
            if 1 <= ch <= total_chapters:
                selected.add(ch)
            else:
                warnings.append(f"Глава {ch} вне диапазона (1-{total_chapters})")

    if warnings and log_func:
        log_func(f"⚠️ Предупреждения при разборе глав: {'; '.join(warnings)}")

    return sorted(selected)