from django.apps import AppConfig
from django.db.models.signals import post_migrate


def init_roles_callback(sender, **kwargs):
    if sender.name == "accounts":
        from accounts.roles import setup_groups_and_permissions

        setup_groups_and_permissions()


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        post_migrate.connect(init_roles_callback, sender=self)
