from django.apps import AppConfig


class FormulasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'formulas'
    verbose_name = '火药配方文献管理'

    def ready(self):
        import formulas.signals
