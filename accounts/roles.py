from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

ADMIN_GROUP_NAME = "Administrator"
OFFICER_GROUP_NAME = "Placement Officers"
STUDENT_GROUP_NAME = "Student"


def setup_groups_and_permissions():
    """Create standard CPMS groups (Administrator, Placement Officers, Student)
    and assign appropriate model permissions.
    """
    admin_group, _ = Group.objects.get_or_create(name=ADMIN_GROUP_NAME)
    officer_group, _ = Group.objects.get_or_create(name=OFFICER_GROUP_NAME)
    student_group, _ = Group.objects.get_or_create(name=STUDENT_GROUP_NAME)

    from accounts.models import Department, StudentProfile
    from recruitment.models import (
        Application,
        Company,
        InterviewRound,
        PlacementDrive,
        PlacementOffer,
    )
    from training.models import TrainingProgram

    # 1. Administrator & Placement Officer permissions:
    # Full management for drives, applications, companies, rounds, offers, programs, students, depts
    admin_models = [
        Department,
        StudentProfile,
        Application,
        Company,
        InterviewRound,
        PlacementDrive,
        PlacementOffer,
        TrainingProgram,
    ]
    for model in admin_models:
        ct = ContentType.objects.get_for_model(model)
        perms = Permission.objects.filter(content_type=ct)
        admin_group.permissions.add(*perms)
        officer_group.permissions.add(*perms)

    # 2. Student permissions:
    # View drives, companies, training programs, departments
    view_models = [PlacementDrive, Company, TrainingProgram, Department]
    for model in view_models:
        ct = ContentType.objects.get_for_model(model)
        perms = Permission.objects.filter(content_type=ct, codename__startswith="view_")
        student_group.permissions.add(*perms)

    # Manage own applications
    app_ct = ContentType.objects.get_for_model(Application)
    app_perms = Permission.objects.filter(
        content_type=app_ct,
        codename__in=["add_application", "change_application", "view_application"],
    )
    student_group.permissions.add(*app_perms)

    # Manage own profile
    prof_ct = ContentType.objects.get_for_model(StudentProfile)
    prof_perms = Permission.objects.filter(
        content_type=prof_ct,
        codename__in=["change_studentprofile", "view_studentprofile"],
    )
    student_group.permissions.add(*prof_perms)

    return admin_group, officer_group, student_group


def assign_student_role(user):
    """Assign student group and ensure non-staff status."""
    student_group, _ = Group.objects.get_or_create(name=STUDENT_GROUP_NAME)
    user.groups.add(student_group)
    if user.is_staff or user.is_superuser:
        user.is_staff = False
        user.is_superuser = False
        user.save(update_fields=["is_staff", "is_superuser"])


def assign_admin_role(user):
    """Assign administrator role and grant staff privileges."""
    admin_group, _ = Group.objects.get_or_create(name=ADMIN_GROUP_NAME)
    user.groups.add(admin_group)
    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])
