from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'

    def ready(self):
        """Standard Django app ready (clean startup)."""
        # Manual SQL overrides removed to prevent RuntimeWarnings and DB locking.
        # Everything is now handled via proper Django Migrations.
        pass
