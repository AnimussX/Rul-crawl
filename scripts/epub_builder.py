from ebooklib import epub
from pathlib import Path

def build_epub(data_dir, title, author, synopsis, chapters, cover_data, used_images):
    book = epub.EpubBook()
    book.set_identifier(f"rulate_{data_dir.name}")
    book.set_title(title)
    book.set_language('ru')
    book.add_author(author)

    if synopsis:
        from bs4 import BeautifulSoup
        plain = BeautifulSoup(synopsis, "lxml").get_text()
        book.add_metadata('DC', 'description', plain)

    if cover_data:
        book.set_cover("cover.jpg", cover_data, create_page=True)

    desc_page = None
    if synopsis:
        desc_page = epub.EpubHtml(
            title='Описание',
            file_name='description.xhtml',
            lang='ru'
        )
        desc_page.content = synopsis
        book.add_item(desc_page)
        print("   ✅ Страница описания создана")

    chapter_objs = []
    for idx, ch_title, content in chapters:
        fname = f"{idx:05d}.xhtml"
        chap = epub.EpubHtml(
            title=ch_title,
            file_name=fname,
            lang='ru'
        )
        chap.content = content
        book.add_item(chap)
        chapter_objs.append(chap)
        print(f"   ✅ Глава {idx} добавлена")

    images_dir = data_dir / "images"
    if images_dir.exists():
        for img_file in images_dir.glob("*"):
            if used_images and img_file.name not in used_images:
                continue
            ext = img_file.suffix.lower()
            if ext in ('.jpg', '.jpeg'):
                media_type = 'image/jpeg'
            elif ext == '.png':
                media_type = 'image/png'
            elif ext == '.gif':
                media_type = 'image/gif'
            elif ext == '.webp':
                media_type = 'image/webp'
            else:
                continue
            with open(img_file, 'rb') as f:
                img_data = f.read()
            img_item = epub.EpubImage()
            img_item.file_name = f"images/{img_file.name}"
            img_item.media_type = media_type
            img_item.content = img_data
            book.add_item(img_item)
            print(f"   ✅ Изображение добавлено: {img_file.name}")
    else:
        print("📦 Папка images не найдена")

    book.toc = tuple(chapter_objs)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    spine = ['nav']
    if cover_data:
        spine.insert(0, 'cover')
    if desc_page:
        spine.insert(1 if cover_data else 0, desc_page)
    for chap in chapter_objs:
        spine.append(chap)
    book.spine = spine

    return book