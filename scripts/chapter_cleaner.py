from bs4 import BeautifulSoup, Comment

def debug_print(msg, debug):
    if debug:
        print(msg)

def extract_image_urls(html):
    soup = BeautifulSoup(html, 'lxml')
    return [img.get('src') for img in soup.find_all('img') if img.get('src')]

def clean_chapter_html(raw_html, chapter_title, image_map=None, debug=False):
    soup = BeautifulSoup(raw_html, 'lxml')

    original_imgs = soup.find_all('img')
    debug_print(f"   🔍 Изначально img тегов: {len(original_imgs)}", debug)

    for tag in soup.find_all(['script', 'style', 'link', 'iframe', 'noscript', 'meta']):
        tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

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
            tag.decompose()

    bad_tags = {
        "address", "amp-auto-ads", "audio", "button", "figcaption",
        "footer", "form", "header", "iframe", "input", "ins", "map",
        "nav", "noscript", "object", "output", "pirate", "script",
        "select", "source", "style", "textarea", "tfoot", "video"
    }
    for tag_name in bad_tags:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    remaining_imgs = soup.find_all('img')
    debug_print(f"   🔍 После удаления мусора осталось img: {len(remaining_imgs)}", debug)

    placeholder_map = {}
    expected_local_names = set(image_map.values()) if image_map else set()

    for img in remaining_imgs:
        src = img.get('src')
        if not src:
            img.decompose()
            continue

        if src.startswith('/'):
            src = 'https://tl.rulate.ru' + src
            debug_print(f"      🔄 Нормализован относительный URL: {src}", debug)

        if src.startswith('images/'):
            local_name = src[7:]
            if local_name in expected_local_names:
                debug_print(f"      ✅ Оставлен локальный img: {src}", debug)
                continue
            else:
                img.decompose()
                debug_print(f"      🗑️ Удалён локальный img с неожиданным именем: {src}", debug)
                continue

        local_name = None
        if image_map:
            if src in image_map:
                local_name = image_map[src]
            else:
                for url, name in image_map.items():
                    if url in src or src in url:
                        local_name = name
                        break

        if local_name:
            placeholder = f"<!--IMG:{local_name}-->"
            placeholder_map[local_name] = placeholder
            img.replace_with(BeautifulSoup(placeholder, 'html.parser'))
            debug_print(f"      🔄 Заменён img {src[:60]}... на плейсхолдер {local_name}", debug)
        else:
            img.decompose()
            debug_print(f"      🗑️ Удалён img без соответствия: {src[:60]}...", debug)

    for elem in soup.find_all():
        if elem.name not in ['br', 'hr', 'img'] and not elem.get_text(strip=True) and not elem.find_all(True):
            elem.decompose()

    for a in soup.find_all('a', href=True):
        if 'rulate.ru' in a['href']:
            a.decompose()
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if 'rulate.ru' in text:
            p.decompose()

    final_html = str(soup)
    for local_name, placeholder in placeholder_map.items():
        img_tag = f'<img src="images/{local_name}" style="max-width:100%; display:block; margin:1em auto;" alt="иллюстрация" />'
        final_html = final_html.replace(placeholder, img_tag)
        debug_print(f"      🔄 Заменён плейсхолдер {local_name} на тег img", debug)

    final_soup = BeautifulSoup(final_html, 'lxml')
    final_imgs = final_soup.find_all('img')
    debug_print(f"   ✅ Финальных img тегов: {len(final_imgs)}", debug)

    return f'<section epub:type="chapter">\n<h1>{chapter_title}</h1>\n{final_html}\n</section>'