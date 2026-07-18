# cli.py

import argparse
import sys
from scripts.download_manager import download_book, DownloadCallbacks


def main():
    parser = argparse.ArgumentParser(
        description="Загрузка новеллы и сборка EPUB (Rulate / Ranobes)."
    )
    parser.add_argument("url", help="Ссылка на новеллу")
    parser.add_argument(
        "-c", "--chapters", default="",
        help="Спецификация глав, например '1-50,55,60-70'. Пусто = все главы."
    )
    parser.add_argument("--login", default=None, help="Логин (если требуется)")
    parser.add_argument("--password", default=None, help="Пароль (если требуется)")
    parser.add_argument(
        "-o", "--target-dir", dest="target_dir", default=None,
        help="Папка для временных файлов/кэша. По умолчанию — из NOVELS_BASE."
    )
    parser.add_argument(
        "-f", "--force", action="store_true",
        help="Принудительно перезагрузить все главы и метаданные"
    )
    parser.add_argument(
        "--ignore-image-errors", action="store_true",
        help="Не прерывать сборку, если часть изображений не загрузилась"
    )
    parser.add_argument(
        "--ignore-errors", action="store_true",
        help="Не прерывать сборку, если часть глав не загрузилась"
    )
    parser.add_argument("--workers", type=int, default=2, help="Потоков для глав (1-5)")
    parser.add_argument("--image-workers", type=int, default=2, help="Потоков для изображений (1-5)")
    parser.add_argument("--image-retries", type=int, default=3, help="Попыток загрузки изображения")
    parser.add_argument("--image-timeout", type=int, default=30, help="Таймаут обычных изображений (сек)")
    parser.add_argument("--slow-image-timeout", type=int, default=120, help="Таймаут медленных хостингов (сек)")
    parser.add_argument("--proxy-file", default=None, help="Файл со списком прокси")
    parser.add_argument("--debug", action="store_true", help="Подробные логи")
    parser.add_argument(
        "--rebuild-only", action="store_true",
        help="Только собрать EPUB из уже загруженного кэша, без обращения к сайту"
    )

    args = parser.parse_args()

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
        callbacks=callbacks,
        rebuild_only=args.rebuild_only,
    )

    if success:
        print(f"\n✅ Готово: {result}")
    else:
        print(f"\n❌ Ошибка: {result}", file=sys.stderr)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()