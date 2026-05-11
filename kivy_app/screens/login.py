from kivymd.uix.screen import MDScreen
from kivymd.app import MDApp
from scripts.auth import save_auth

class LoginScreen(MDScreen):
    def do_login(self):
        login = self.ids.login_field.text
        password = self.ids.pass_field.text
        if login and password:
            save_auth(login, password)
            app = MDApp.get_running_app()
            app.LOGIN, app.PASSWORD = login, password
            app.sm.current = 'main_menu'