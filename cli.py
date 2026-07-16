# cli.py

import argparse
import sys
from scripts.download_manager import download_book, DownloadCallbacks

def main():
    parser = argparse.ArgumentParser(...) # как раньше
    args = parser.parse_args()

    # Преобразуем аргументы
    callbacks = DownloadCallbacks(log_callback=print)
    success, result = download_book(
        url=args.url,
        chapters_spec=args.chapters,
        login=args.login,
        password=args.password,
        target_dir=args.target_dir,
        force=args.force,
        ignore_image_errors=args.ignore_image_errors,
        ignore_errors=args.ignore_errors,
        workers=args.workers,
        image_workers=args.image_workers,
        image_retries=args.image_retries,
        image_timeout=args.image_timeout,
        slow_image_timeout=args.slow_image_timeout,
        proxy_file=args.proxy_file,
        debug=args.debug,
        callbacks=callbacks
    )
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()