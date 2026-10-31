from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from accounts.roles import assign_admin_role, setup_groups_and_permissions

User = get_user_model()


class Command(BaseCommand):
    help = "Creates or promotes an administrator account using Django superuser privileges."

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, help="Username for the administrator")
        parser.add_argument("--email", type=str, help="Email for the administrator")
        parser.add_argument("--password", type=str, help="Password for the administrator")

    def handle(self, *args, **options):
        setup_groups_and_permissions()

        username = options.get("username")
        email = options.get("email") or ""
        password = options.get("password")

        if not username:
            username = input("Username: ").strip()
        if not email and not options.get("email"):
            email = input("Email address: ").strip()
        if not password:
            import getpass
            password = getpass.getpass("Password: ")

        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        user.is_staff = True
        user.is_superuser = True
        if email:
            user.email = email
        if password:
            user.set_password(password)
        user.save()

        assign_admin_role(user)

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} administrator '{username}' with superuser and staff privileges."
            )
        )
