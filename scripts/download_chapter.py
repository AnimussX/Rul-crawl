import requests

def download_cover(url, output_path):
    try:
        r = requests.get(url, stream=True, timeout=15)
        r.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"⚠️ Не удалось скачать обложку {url}: {e}")
        return False