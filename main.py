# main.py (корень проекта)

import sys

# --- ЭКСТРЕННАЯ ЗАПИСЬ ДО ВСЕХ ИМПОРТОВ ---
try:
    with open("/sdcard/debug_log.txt", "w") as f:
        f.write("Step 0: main.py started\n")
except:
    pass

try:
    with open("/sdcard/debug_log.txt", "a") as f:
        f.write("Step 1: importing main_kivy...\n")
    from kivy_app.main_kivy import RulateCrawlerApp

    with open("/sdcard/debug_log.txt", "a") as f:
        f.write("Step 2: import done, running...\n")
    RulateCrawlerApp().run()

    with open("/sdcard/debug_log.txt", "a") as f:
        f.write("Step 3: app finished normally\n")
except BaseException as e:
    try:
        with open("/sdcard/debug_log.txt", "a") as f:
            f.write(f"CRASH in main.py: {type(e).__name__}: {e}\n")
            f.write(f"sys.path: {sys.path}\n")
    except:
        pass
    raise