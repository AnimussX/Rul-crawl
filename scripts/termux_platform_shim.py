import json
import os
import sys


def apply_seleniumbase_platform_shim():
    if sys.platform != "android":
        return

    patches = json.loads(os.environ.get("PATCHES_JSON", "[]"))
    if "seleniumbase_platform_shim" not in patches:
        return

    print("Android platform detected. Reporting platform as 'linux' for SeleniumBase import compatibility.")
    sys.platform = "linux"
