import hashlib
from bs4 import BeautifulSoup, Comment

def clean_chapter_html(raw_html, chapter_title, image_map=None, debug=False):
    soup = BeautifulSoup(raw_html, 'html.parser')
    
    # 1. Замена внешних изображений на текстовые метки
    for img in soup.find_all('img'):
        if img is None:
            continue
        src = img.get('src')
        if not src:
            img.decompose()
            continue
        # Нормализация относительных URL
        if src.startswith('/'):
            src = 'https://tl.rulate.ru' + src
        # Локальные изображения (уже скачанные) не трогаем
        if src.startswith('images/'):
            continue
        url_hash = hashlib.md5(src.encode()).hexdigest()
        img.replace_with(f"[[IMG:{url_hash}]]")
        if debug:
            print(f"      Заменён img на метку: [[IMG:{url_hash}]]")

    # 2. Удаление скриптов, стилей, мета-тегов, iframe и прочего мусора
    for tag in soup.find_all(['script', 'style', 'link', 'meta', 'iframe', 'noscript', 'audio', 'video', 'canvas', 'svg', 'button', 'input', 'select', 'textarea', 'form']):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # 3. Удаление рекламных блоков по селекторам
    bad_selectors = [
        ".adblock-service", ".sharedaddy", ".saboxplugin-wrap", ".adbox",
        ".ads-middle", ".ads", ".adsbygoogle", ".adsense-code",
        ".cb_p6_patreon_button", ".code-block", ".ezoic-ad-adaptive",
        ".ezoic-ad", ".ezoic-adpicker-ad", ".googlepublisherads",
        ".inline-ad-slot", ".jp-relatedposts", ".sharedaddy",
        ".wp-post-navigation", "a[href*='patreon.com']", "a[href*='paypal.me']"
    ]
    for selector in bad_selectors:
        for tag in soup.select(selector):
            if tag:
                tag.decompose()

    # 4. Удаление нежелательных тегов (навигация, подвал и т.п.)
    for tag_name in ['footer', 'header', 'nav', 'aside', 'address']:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # 5. Удаление ссылок на rulate.ru (но не трогаем метки)
    for a in soup.find_all('a', href=True):
        if 'rulate.ru' in a['href']:
            a.decompose()
    for p in soup.find_all('p'):
        if 'rulate.ru' in p.get_text(strip=True):
            p.decompose()

    final_html = str(soup)
    return f'<section epub:type="chapter">\n<h1>{chapter_title}</h1>\n{final_html}\n</section>'