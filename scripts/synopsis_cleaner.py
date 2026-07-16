# scripts/synopsis_cleaner.py

import re
from bs4 import BeautifulSoup

def clean_synopsis_html(raw_html: str) -> str:
    if not raw_html:
        return ""

    soup = BeautifulSoup(raw_html, 'lxml')

    # 1. Удаляем явный мусор: скрипты, стили, iframe, формы
    for tag in soup.find_all(['script', 'style', 'iframe', 'noscript', 'meta', 'link', 'button', 'input', 'select', 'textarea']):
        tag.decompose()

    # 2. Удаляем классы-мусор (кнопки, рейтинги, реклама)
    junk_classes = [
        'rating-block', 'btn-toolbar', 'btn-group', 'social-likes', 'share-buttons',
        'advert', 'ads', 'slick', 'pull-right', 'alert', 'well', 'panel', 'reviews', 'comments',
        'icon', 'badge', 'cat', 'pull-left', 'row-fluid', 'span2', 'span5', 'span7'
    ]
    for cls in junk_classes:
        for tag in soup.select(f'.{cls}'):
            tag.decompose()

    # 3. Удаляем элементы <i>, которые не содержат текста и не содержат картинок
    for i in soup.find_all('i'):
        if not i.get_text(strip=True) and not i.find('img'):
            i.decompose()

    # 4. Удаляем параграфы с мусорными фразами, но НЕ те, что содержат изображения
    bad_phrases = [
        'качество перевода', 'рейтинг', 'оценка', 'поделиться', 'лайк', 'дизлайк',
        'патреон', 'paypal', 'donate', 'поддержать', '★', '♥', 'rc)', 'rulate', 'написать отзыв',
        'сообщить модератору', 'купить книгу', 'спонсор'
    ]
    for p in soup.find_all('p'):
        if p.find('img'):
            continue  # НЕ УДАЛЯЕМ параграфы, содержащие картинки
        text = p.get_text(' ', strip=True).lower()
        if any(phrase in text for phrase in bad_phrases):
            p.decompose()

    # 5. Удаляем заголовки h2/h3/h4 с мусорными словами (Рецензии, Отзывы и т.п.)
    bad_headings = ['рецензии', 'отзывы', 'обсуждение', 'что думаете', 'поддержать']
    for h in soup.find_all(['h2', 'h3', 'h4']):
        if h.get_text(strip=True).lower() in bad_headings:
            h.decompose()

    # 6. Удаляем пустые параграфы (без текста и без изображений)
    for p in soup.find_all('p'):
        if not p.get_text(strip=True) and not p.find('img'):
            p.decompose()

    # 7. Нормализуем изображения: заменяем data-src на src, убираем лишние атрибуты
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src') or img.get('data-original') or img.get('data-lazy')
        if not src:
            img.decompose()
            continue
        if src.startswith('//'):
            src = 'https:' + src
        img['src'] = src
        for attr in ['srcset', 'data-src', 'data-original', 'data-lazy', 'loading', 'decoding']:
            if attr in img.attrs:
                del img.attrs[attr]
        if 'alt' not in img.attrs:
            img['alt'] = 'иллюстрация'

    # 8. Восстанавливаем структуру: заменяем ненужные div на p (если внутри нет других блоков)
    for div in soup.find_all('div'):
        if not div.find('div') and not div.find('ul') and not div.find('ol') and div.get_text(strip=True):
            div.name = 'p'

    # 9. Собираем HTML
    html = str(soup)
    # Убираем множественные переносы
    html = re.sub(r'\n{3,}', '\n\n', html)
    # Удаляем лишние пробелы между тегами
    html = re.sub(r'>\s+<', '><', html)
    # Удаляем пустые строки в начале/конце
    html = html.strip()

    # Если после всех чисток HTML стал пустым, пробуем извлечь все параграфы, содержащие картинки
    if len(html) < 20:
        original = BeautifulSoup(raw_html, 'lxml')
        # Удаляем только явно мусорные блоки по классам
        for cls in junk_classes:
            for tag in original.select(f'.{cls}'):
                tag.decompose()
        # Собираем параграфы с картинками или достаточно длинные
        good_paragraphs = []
        for p in original.find_all('p'):
            if p.find('img'):
                good_paragraphs.append(str(p))
            elif len(p.get_text(strip=True)) > 50:
                # дополнительно проверяем на мусорные фразы
                text = p.get_text(strip=True).lower()
                if not any(phrase in text for phrase in bad_phrases):
                    good_paragraphs.append(str(p))
        if good_paragraphs:
            return '\n'.join(good_paragraphs)
        else:
            # возвращаем хотя бы первые 500 символов исходного HTML
            return raw_html[:500]

    return html


def get_clean_meta_description(html: str, max_length: int = 500) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, 'lxml')
    text = soup.get_text(separator=' ', strip=True)
    text = re.sub(r'\s+', ' ', text)
    if len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + '…'
    return text