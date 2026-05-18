from kivymd.uix.screen import MDScreen
from kivymd.app import MDApp
from kivy.lang import Builder
from scripts.auth import save_auth

# Встроенная KV-разметка
Builder.load_string('''
<LoginScreen>:
    MDBoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(10)
        MDLabel:
            text: "Введите логин и пароль от Rulate"
            halign: 'center'
        MDTextField:
            id: login_field
            hint_text: "Логин"
        MDTextField:
            id: pass_field
            hint_text: "Пароль"
            password: True
        MDRaisedButton:
            text: "Сохранить"
            on_release: root.do_login()
''')

class LoginScreen(MDScreen):
    def do_login(self):
        login = self.ids.login_field.text
        password = self.ids.pass_field.text
        if login and password:
            save_auth(login, password)
            app = MDApp.get_running_app()
            app.LOGIN, app.PASSWORD = login, password
            app.sm.current = 'main_menu'