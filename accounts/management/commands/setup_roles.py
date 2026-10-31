from django.core.management.base import BaseCommand
from accounts.roles import setup_groups_and_permissions


class Command(BaseCommand):
    help = "Sets up standard Django Groups and Permissions for CPMS roles (Administrator, Student, Placement Officers)."

    def handle(self, *args, **options):
        self.stdout.write("Initializing CPMS Groups and Permissions...")
        admin_group, officer_group, student_group = setup_groups_and_permissions()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully configured roles:\n"
                f" - {admin_group.name} ({admin_group.permissions.count()} permissions)\n"
                f" - {officer_group.name} ({officer_group.permissions.count()} permissions)\n"
                f" - {student_group.name} ({student_group.permissions.count()} permissions)"
            )
        )
