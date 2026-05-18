import json
from pathlib import Path
from bs4 import BeautifulSoup

def process_synopsis_images(crawler, synopsis, data_dir):
    from .lncrawl_stubs import Chapter
    temp_chapter = Chapter(id=0)
    temp_chapter.body = synopsis
    temp_chapter.images = {}
    crawler.output_path = str(data_dir)
    crawler.extract_chapter_images(temp_chapter)
    return temp_chapter.body, temp_chapter.images

def save_synopsis_cache(data_dir, synopsis, images_dict):
    synopsis_file = data_dir / "synopsis_processed.xhtml"
    images_file = data_dir / "synopsis_images.json"
    with open(synopsis_file, 'w', encoding='utf-8') as f:
        f.write(synopsis)
    with open(images_file, 'w', encoding='utf-8') as f:
        json.dump(images_dict, f, ensure_ascii=False, indent=2)

def load_synopsis_cache(data_dir):
    synopsis_file = data_dir / "synopsis_processed.xhtml"
    images_file = data_dir / "synopsis_images.json"
    if not synopsis_file.exists():
        return None, {}
    with open(synopsis_file, 'r', encoding='utf-8') as f:
        synopsis = f.read()
    images_dict = {}
    if images_file.exists():
        with open(images_file, 'r', encoding='utf-8') as f:
            images_dict = json.load(f)
    return synopsis, images_dict

def add_base_tag_to_html(html):
    if '<head>' not in html:
        html = html.replace('<html', '<html><head><meta charset="utf-8"/></head>', 1)
    if '<base href="/"' not in html:
        html = html.replace('<head>', '<head><base href="/" />')
    return html

def ensure_image_in_synopsis(synopsis, images_from_synopsis, rename_map):
    import re
    if not images_from_synopsis or not rename_map:
        return synopsis, False

    # Если уже есть img, ничего не делаем (предполагаем, что они уже обработаны)
    if re.search(r'<img', synopsis):
        return synopsis, False

    # Ищем первое изображение из словаря, для которого есть новое имя
    for old_fn in images_from_synopsis:
        if old_fn in rename_map:
            new_fn = rename_map[old_fn]
            img_tag = f'<div style="text-align:center; margin:1em 0;"><img src="images/{new_fn}" alt="Иллюстрация" style="max-width:100%;"/></div>'
            # Пытаемся вставить после заголовка h1, если он есть
            if '<h1>' in synopsis and '</h1>' in synopsis:
                # Вставляем после первого закрывающего </h1>
                synopsis = synopsis.replace('</h1>', f'</h1>\n{img_tag}', 1)
            else:
                # Иначе вставляем в начало
                synopsis = img_tag + synopsis
            return synopsis, True
    return synopsis, False