import time
import io
from pathlib import Path
from urllib.parse import urljoin
from PIL import Image
from bs4 import BeautifulSoup

def download_all_images(crawler, images_dict, images_dir, max_retries=2):
    """
    Скачивает изображения. п∙сли сервер возвращает HTML, пятается извлечь ссялку на изображение из страниця.
    Возвращает словарь {старое_имя: новое_имя} для обновления HTML глав.
    """
    rename_map = {}
    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    for old_filename, url in images_dict.items():
        success = False
        current_url = url
        for attempt in range(max_retries + 1):
            try:
                print(f"   П÷■≈ Попятка {attempt+1} для {old_filename} ({current_url[:80]}...)")
                
                headers = {
                    'Referer': 'https://tl.rulate.ru/',
                    'User-Agent': crawler.session.headers.get('User-Agent', 'Mozilla/5.0'),
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                }
                
                resp = crawler.session.get(current_url, stream=True, timeout=15, allow_redirects=True, headers=headers)
                resp.raise_for_status()

                content_type = resp.headers.get('Content-Type', '').lower()
                
                # п∙сли я█то HTML, пробуем извлечь ссялку на изображение
                if 'html' in content_type:
                    print(f"   Получен HTML, пятаемся извлечь изображение...")
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    
                    # Ищем meta og:image
                    og_image = soup.find('meta', property='og:image')
                    if og_image and og_image.get('content'):
                        new_url = og_image['content']
                        print(f"      Найдена og:image: {new_url[:80]}")
                        current_url = new_url
                        if attempt < max_retries:
                            time.sleep(2)
                            continue
                    
                    # Ищем первяй тег img с src
                    img_tag = soup.find('img')
                    if img_tag and img_tag.get('src'):
                        new_url = img_tag['src']
                        if not new_url.startswith('http'):
                            new_url = urljoin(current_url, new_url)
                        print(f"      Найдена img src: {new_url[:80]}")
                        current_url = new_url
                        if attempt < max_retries:
                            time.sleep(2)
                            continue
                    
                    # п∙сли ничего не нашли, соХраняем для отладки
                    debug_path = images_dir / f"debug_{old_filename}.html"
                    with open(debug_path, 'wb') as f:
                        f.write(resp.content)
                    print(f"      Не удалось извлечь изображение, ответ соХранен в {debug_path}")
                    break

                # Проверяем, что я█то действительно изображение
                if not content_type.startswith('image/'):
                    print(f"   Content-Type не image: {content_type}")
                    debug_path = images_dir / f"debug_{old_filename}.bin"
                    with open(debug_path, 'wb') as f:
                        f.write(resp.content)
                    print(f"      Ответ соХранен в {debug_path}")
                    break

                # Определяем формат и соХраняем
                if 'image/jpeg' in content_type:
                    ext, fmt = '.jpg', 'JPEG'
                elif 'image/png' in content_type:
                    ext, fmt = '.png', 'PNG'
                elif 'image/gif' in content_type:
                    ext, fmt = '.gif', 'GIF'
                elif 'image/webp' in content_type:
                    ext, fmt = '.webp', 'WEBP'
                else:
                    # Fallback на расширение URL
                    url_lower = current_url.lower()
                    if '.png' in url_lower:
                        ext, fmt = '.png', 'PNG'
                    elif '.gif' in url_lower:
                        ext, fmt = '.gif', 'GIF'
                    elif '.webp' in url_lower:
                        ext, fmt = '.webp', 'WEBP'
                    else:
                        ext, fmt = '.jpg', 'JPEG'

                base = old_filename.replace('.jpg', '')
                new_filename = base + ext
                img_path = images_dir / new_filename

                img = Image.open(io.BytesIO(resp.content))
                if fmt == 'JPEG' and img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                img.save(img_path, format=fmt, optimize=True)

                print(f"   {new_filename} соХранен ({img_path.stat().st_size} байт)")
                rename_map[old_filename] = new_filename
                success = True
                break

            except Exception as e:
                print(f"   Попятка {attempt+1} ошибка: {e}")
                if attempt < max_retries:
                    time.sleep(3)
                else:
                    print(f"   ! Не удалось загрузить {old_filename} после {max_retries+1} попяток")

    return rename_map