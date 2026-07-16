import json
import os

AUTH_FILE = os.path.expanduser("~/.lncrawl.auth.json")

def load_auth():
    """Загружает общие логин/пароль (Rulate)."""
    if os.path.isfile(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('login'), data.get('password')
        except (json.JSONDecodeError, KeyError):
            return None, None
    return None, None

def save_auth(login, password):
    """Сохраняет общие логин/пароль, сохраняя уже существующие ranobes-данные."""
    data = {}
    if os.path.isfile(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass
    data['login'] = login
    data['password'] = password
    with open(AUTH_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.chmod(AUTH_FILE, 0o600)

def load_ranobes_auth():
    """Загружает отдельные логин/пароль для ranobes.com."""
    if os.path.isfile(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('ranobes_login'), data.get('ranobes_password')
        except (json.JSONDecodeError, KeyError):
            return None, None
    return None, None

def save_ranobes_auth(login, password):
    """Сохраняет учётные данные для ranobes.com, не трогая общие."""
    data = {}
    if os.path.isfile(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass
    data['ranobes_login'] = login
    data['ranobes_password'] = password
    with open(AUTH_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.chmod(AUTH_FILE, 0o600)