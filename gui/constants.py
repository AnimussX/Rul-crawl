# gui/constants.py

SECTIONS = [
    ("Английские", "Английские"),
    ("Китайские", "Китайские"),
    ("Корейские", "Корейские"),
    ("Русские", "Русские"),
    ("Японские", "Японские"),
    ("(18+)", "(18+)"),
    ("Разные", "Разные"),
]

SOURCE_LABELS = {
    "rulate": "Rulate (tl.rulate.ru)",
    "ranobes": "Ranobes.com",
}


def build_output_path(base_dir: str, section: str, safe_title: str) -> str:
    """Единая логика формирования пути для готового EPUB."""
    import os
    if section and section != "Разные":
        return os.path.join(base_dir, section, safe_title)
    return os.path.join(base_dir, safe_title)