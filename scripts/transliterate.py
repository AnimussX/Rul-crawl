import re
from transliterate import translit

WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

def slugify(text, default="unnamed", max_length=80):
    """
    Безопасный slug:
    - принудительно русский
    - пробелы -> _
    - только a-z0-9_
    - ограничение длины
    - защита от Windows-имён
    """

    if not text or not isinstance(text, str):
        return default

    original = text

    # Транслитерация (принудительно ru)
    try:
        text = translit(text, 'ru', reversed=True)
    except Exception:
        pass

    # Только буквы/цифры/пробелы/дефисы
    text = re.sub(r'[^\w\s-]', '', text)

    # Пробелы и дефисы -> _
    text = re.sub(r'[-\s]+', '_', text)

    # Нижний регистр
    text = text.lower().strip('_')

    # Оставляем только ascii a-z0-9_
    text = re.sub(r'[^a-z0-9_]', '', text)

    # Ограничение длины
    text = text[:max_length].rstrip('_')

    if not text:
        text = default

    # Windows reserved names
    if text in WINDOWS_RESERVED:
        text = f"{text}_file"

    return text