import requests

def download_cover(url, output_path, session=None):
    """
    Скачивает обложку по URL.
    Если передана сессия (requests.Session), использует её (с куками и заголовками).
    """
    try:
        if session:
            r = session.get(url, stream=True, timeout=15)
        else:
            r = requests.get(url, stream=True, timeout=15)
        r.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"⚠️ Не удалось скачать обложку {url}: {e}")
        return False