# scripts/auth.py
import os

# Значение будет установлено при инициализации приложения
AUTH_FILE = None

def load_auth():
    if AUTH_FILE and os.path.isfile(AUTH_FILE):
        data = {}
        with open(AUTH_FILE, 'r') as f:
            exec(f.read(), {}, data)
        return data.get('LOGIN'), data.get('PASSWORD')
    return None, None

def save_auth(login, password):
    if not AUTH_FILE:
        return
    with open(AUTH_FILE, 'w') as f:
        f.write(f"LOGIN='{login}'\nPASSWORD='{password}'\n")
    os.chmod(AUTH_FILE, 0o600)