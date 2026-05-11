import re

def html_to_text(html):
    """Преобразует HTML в читаемый текст с сохранением абзацев и переносов строк."""
    if not html:
        return ""
    # Заменяем <br> на \n
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    # Заменяем закрывающие теги </p> на двойной перенос строки (новый абзац)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    # Удаляем все остальные HTML-теги
    text = re.sub(r'<[^>]+>', '', text)
    # Очищаем лишние пробелы
    text = re.sub(r'[ \t]+', ' ', text)
    # Убираем пробелы в начале и конце строк
    text = re.sub(r' *\n *', '\n', text)
    # Схлопываем множественные переносы до максимум двух
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()