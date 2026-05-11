[app]
title = Rulate Crawler
package.name = rulatecrawler
package.domain = org.yourname
version = 1.0
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,pkl,xhtml,css

# libxml2 и libxslt в начале, чтобы собрались первыми
requirements = python3==3.11.5,hostpython3==3.11.5,libxml2,libxslt,kivy,kivymd,pillow,requests,openssl,beautifulsoup4,lxml==4.9.2,ebooklib,cloudscraper

orientation = portrait
fullscreen = 0
android.api = 31
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions = INTERNET, MANAGE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE
android.allow_backup = True

icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png

p4a.branch = master

log_level = 2
warn_on_root = 0