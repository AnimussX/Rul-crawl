from pythonforandroid.recipes.lxml import LxmlRecipe as BaseLxmlRecipe

class LxmlRecipe(BaseLxmlRecipe):
    """Переопределённый рецепт lxml для статической сборки."""

    def build_compiled_components(self, arch):
        env = self.get_recipe_env(arch)
        # Указываем путь к статическим библиотекам
        env['LXML_STATIC_LIB_DIRS'] = ':'.join([
            self.ctx.get_libs_dir(arch.arch),
            self.ctx.libs_dir,  # на всякий случай
        ])
        # Включаем статическую линковку
        env['LXML_STATIC_DEPS'] = 'true'
        return super().build_compiled_components(arch)

recipe = LxmlRecipe()