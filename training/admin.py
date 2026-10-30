
from django.contrib import admin
from .models import (
    TrainingProgram,
    TrainingEnrollment,
    TrainingAttendance,
)


@admin.register(TrainingProgram)
class TrainingProgramAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "trainer",
        "mode",
        "start_date",
        "end_date",
        "status",
    )
    list_filter = ("mode", "status")
    search_fields = ("title", "trainer")
    ordering = ("-start_date",)


@admin.register(TrainingEnrollment)
class TrainingEnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "program",
        "attendance_percentage",
        "assessment_score",
        "completion_status",
    )
    list_filter = ("completion_status", "program")
    search_fields = (
        "student__usn",
        "program__title",
    )


@admin.register(TrainingAttendance)
class TrainingAttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "enrollment",
        "session_date",
        "status",
    )
    list_filter = ("status", "session_date")
    search_fields = ("enrollment__student__usn",)
