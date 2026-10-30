from django.contrib import admin
from .models import Department, StudentProfile


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        "usn",
        "user",
        "department",
        "graduation_year",
        "cgpa",
        "active_backlogs",
        "consent_version",
    )

    readonly_fields = ("consent_accepted_at", "consent_version")

    search_fields = (
        "usn",
        "user__first_name",
        "user__last_name",
        "user__email",
    )

    list_filter = (
        "department",
        "graduation_year",
    )

    ordering = ("usn",)