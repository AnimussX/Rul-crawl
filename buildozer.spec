[app]
title = Rulate Crawler
package.name = rulatecrawler
package.domain = org.yourname
version = 1.0
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,pkl,xhtml,css
requirements = python3,kivy,kivymd,pillow,requests,beautifulsoup4,lxml,ebooklib,cloudscraper
orientation = portrait
fullscreen = 0
android.api = 33
android.minapi = 21
android.ndk = 27c
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions = INTERNET, MANAGE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE
android.allow_backup = True

icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png

log_level = 2
warn_on_root = 0

p4a.source_dir = /home/runner/work/Rul-crawl/Rul-crawl/.buildozer/android/platform/python-for-android