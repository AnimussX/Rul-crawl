import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import io
import requests
from PIL import Image
from tqdm import tqdm
from bs4 import BeautifulSoup
from urllib.parse import urljoin

POSSIBLE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']

# Хосты, на которых нужно отключить проверку SSL
SSL_OFF_HOSTS = ['mykaleidoscope.ru', 'img.91yu.com']

def check_existing_file(images_dir, base_name):
    """Проверяет, существует ли уже файл с базовым именем и любым допустимым расширением."""
    for ext in POSSIBLE_EXTENSIONS:
        candidate = images_dir / f"{base_name}{ext}"
        if candidate.exists():
            try:
                with Image.open(candidate) as test_img:
                    test_img.verify()
                return candidate.name, candidate
            except Exception:
                candidate.unlink()
    return None, None

def download_one(crawler, old_filename, url, images_dir, max_retries=3, default_timeout=30, slow_hosts=None, slow_timeout=120, debug=False, pbar=None, progress_callback=None):
    """
    Скачивает одно изображение.
    Для внешних хостов (не rulate) использует отдельные заголовки и умеет извлекать изображение из HTML-страницы.
    """
    if slow_hosts is None:
        slow_hosts = ['i.ibb.co', 'ibb.co', 'postimages.org', 'image.ibb.co', 'imgbb.com']
    
    # Определяем таймаут в зависимости от хоста
    timeout = slow_timeout if any(host in url for host in slow_hosts) else default_timeout
    
    base_name = old_filename.rsplit('.', 1)[0]

    # Проверяем, не скачано ли уже
    existing_name, existing_path = check_existing_file(images_dir, base_name)
    if existing_name:
        if debug:
            print(f"      ⏭️ Изображение уже скачано: {existing_name}")
        if pbar:
            pbar.update(1)
        if progress_callback:
            progress_callback(old_filename, existing_name, None)
        return old_filename, existing_name, None

    # Определяем, внешний ли хост (не rulate)
    is_external = not any(host in url for host in ['rulate.ru', 'tl.rulate.ru'])

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                delay = (2 ** attempt) + random.uniform(0, 1)
                if debug:
                    print(f"      ⏳ Задержка {delay:.1f}с перед повторной попыткой {attempt+1}")
                time.sleep(delay)

            if is_external:
                # Для внешних хостингов используем отдельную сессию с заголовками
                # В зависимости от попытки меняем заголовки для обхода блокировок
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Referer': 'https://imgur.com/',
                }
                
                if attempt == 0:
                    headers['Accept'] = 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
                elif attempt == 1:
                    headers['Accept'] = '*/*'
                    headers['Accept-Encoding'] = 'gzip, deflate, br'
                elif attempt == 2:
                    headers['Accept'] = 'image/webp,image/apng,image/*,*/*;q=0.8'
                    headers['Accept-Encoding'] = 'identity'
                else:
                    headers['Accept'] = 'image/jpeg,image/png,image/gif,image/webp,*/*'
                    headers['Cache-Control'] = 'no-cache'
                
                # Для проблемных хостов добавляем Host и отключаем SSL
                verify_ssl = not any(host in url for host in SSL_OFF_HOSTS)
                if not verify_ssl:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    if parsed.hostname:
                        headers['Host'] = parsed.hostname
                
                session = requests.Session()
                
                try:
                    resp = session.get(url, headers=headers, timeout=timeout, stream=True, verify=verify_ssl)
                    resp.raise_for_status()
                except requests.exceptions.SSLError as ssl_err:
                    if verify_ssl:
                        # Если SSL-ошибка и мы ещё не пробовали без проверки, пробуем ещё раз с verify=False
                        if debug:
                            print(f"      ⚠️ SSL ошибка, пробуем без проверки сертификата: {ssl_err}")
                        resp = session.get(url, headers=headers, timeout=timeout, stream=True, verify=False)
                        resp.raise_for_status()
                    else:
                        raise
                finally:
                    session.close()

                # Если получили 418 (I'm a teapot) – вероятно, сервер блокирует бота. Считаем временной ошибкой и пробуем снова
                if resp.status_code == 418:
                    raise Exception(f"HTTP 418 - сервер отклонил запрос (попытка {attempt+1})")

                content_type = resp.headers.get('Content-Type', '')

                # Если сервер вернул HTML, попытаемся извлечь изображение из meta-тегов
                if 'text/html' in content_type:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    og_image = soup.find('meta', property='og:image')
                    if og_image and og_image.get('content'):
                        new_url = og_image['content']
                        if debug:
                            print(f"      🔄 Найдено изображение в og:image: {new_url}")
                        # Повторяем запрос к новому URL
                        session = requests.Session()
                        verify_ssl = not any(host in new_url for host in SSL_OFF_HOSTS)
                        try:
                            resp = session.get(new_url, headers=headers, timeout=timeout, stream=True, verify=verify_ssl)
                            resp.raise_for_status()
                        finally:
                            session.close()
                        content_type = resp.headers.get('Content-Type', '')
                    else:
                        img = soup.find('img')
                        if img and img.get('src'):
                            new_url = img['src']
                            if not new_url.startswith('http'):
                                new_url = urljoin(url, new_url)
                            if debug:
                                print(f"      🔄 Найдено изображение в теге img: {new_url}")
                            session = requests.Session()
                            verify_ssl = not any(host in new_url for host in SSL_OFF_HOSTS)
                            try:
                                resp = session.get(new_url, headers=headers, timeout=timeout, stream=True, verify=verify_ssl)
                                resp.raise_for_status()
                            finally:
                                session.close()
                            content_type = resp.headers.get('Content-Type', '')
                        else:
                            raise Exception(f"Не удалось найти изображение на странице, URL: {url}")

                if not content_type.startswith('image/'):
                    snippet = resp.content[:200].decode('utf-8', errors='ignore')
                    raise Exception(f"Неверный Content-Type: {content_type}, начало ответа: {snippet}")

                img = Image.open(io.BytesIO(resp.content))
            else:
                # Для rulate используем сессию краулера (с куками)
                if hasattr(crawler, 'session'):
                    resp = crawler.session.get(url, timeout=timeout)
                    if resp.status_code != 200:
                        raise Exception(f"HTTP {resp.status_code}")
                    content_type = resp.headers.get('Content-Type', '')
                    if not content_type.startswith('image/'):
                        snippet = resp.content[:200].decode('utf-8', errors='ignore')
                        raise Exception(f"Неверный Content-Type: {content_type}, начало ответа: {snippet}")
                    img = Image.open(io.BytesIO(resp.content))
                else:
                    # Если у краулера нет сессии (например, Selenium) – используем его метод
                    img = crawler.download_image(url)
                    if img is None:
                        raise Exception("Не удалось скачать (вернулся None)")

            if img.size == (0, 0):
                raise Exception("Изображение имеет нулевой размер")

            # Определяем формат и сохраняем
            fmt = img.format.lower() if img.format else 'jpeg'
            if fmt in ('jpeg', 'jpg'):
                ext = '.jpg'
            elif fmt == 'png':
                ext = '.png'
            elif fmt == 'gif':
                ext = '.gif'
            elif fmt == 'webp':
                ext = '.webp'
            else:
                ext = '.jpg'
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')

            if ext == '.jpg' and img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            new_filename = base_name + ext
            img_path = images_dir / new_filename

            save_kwargs = {'optimize': True}
            if fmt in ('jpeg', 'png', 'gif', 'webp'):
                img.save(img_path, format=fmt.upper(), **save_kwargs)
            else:
                img.save(img_path, format='JPEG', **save_kwargs)

            # Проверка сохранённого файла
            if not img_path.exists() or img_path.stat().st_size == 0:
                raise Exception("Файл не сохранён или пустой")
            try:
                with Image.open(img_path) as test_img:
                    test_img.verify()
            except Exception as e:
                img_path.unlink()
                raise Exception(f"Повреждённый файл: {e}")

            if pbar:
                pbar.update(1)
            if progress_callback:
                progress_callback(old_filename, new_filename, None)
            return old_filename, new_filename, None

        except requests.exceptions.Timeout:
            error = f"Таймаут (>{timeout}с)"
            if attempt < max_retries:
                if debug:
                    print(f"      ⏰ Таймаут {old_filename}, повтор {attempt+2}")
                continue
            else:
                if pbar:
                    pbar.update(1)
                if progress_callback:
                    progress_callback(old_filename, None, error)
                return old_filename, None, error

        except Exception as e:
            error = str(e)
            if hasattr(e, 'response') and e.response is not None:
                error += f" (статус: {e.response.status_code})"
            if attempt < max_retries:
                if debug:
                    print(f"      ⚠️ Попытка {attempt+1}/{max_retries+1} для {old_filename} не удалась: {error}")
                continue
            else:
                if hasattr(e, 'response') and e.response:
                    debug_path = images_dir / f"debug_{old_filename}.bin"
                    with open(debug_path, 'wb') as f:
                        f.write(e.response.content)
                    error += f" (сырой ответ сохранён в {debug_path})"
                if pbar:
                    pbar.update(1)
                if progress_callback:
                    progress_callback(old_filename, None, error)
                return old_filename, None, error

def download_all_images(crawler, images_dict, images_dir, max_workers=2, max_retries=3, default_timeout=30, slow_hosts=None, slow_timeout=120, debug=False, progress_callback=None):
    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    rename_map = {}
    failed = []

    total = len(images_dict)
    with tqdm(total=total, desc="📸 Загрузка изображений", unit="файл", disable=debug) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_img = {
                executor.submit(download_one, crawler, old_fn, url, images_dir, max_retries, default_timeout, slow_hosts, slow_timeout, debug, pbar, progress_callback): old_fn
                for old_fn, url in images_dict.items()
            }

            for future in as_completed(future_to_img):
                old_fn, new_fn, error = future.result()
                if error:
                    failed.append(old_fn)
                else:
                    rename_map[old_fn] = new_fn

    return rename_map, failed