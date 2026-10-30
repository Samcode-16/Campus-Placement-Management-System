from django.contrib import admin
from .models import (
    Company,
    PlacementDrive,
    Application,
    InterviewRound,
    PlacementOffer,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "industry", "contact_email")
    search_fields = ("name", "industry")
    ordering = ("name",)


@admin.register(PlacementDrive)
class PlacementDriveAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "category",
        "package_lpa",
        "status",
        "drive_date",
    )
    list_filter = ("category", "status", "company")
    search_fields = ("title", "company__name")
    filter_horizontal = ("eligible_departments",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("student", "drive", "status", "applied_at")
    list_filter = ("status", "drive__category")
    search_fields = ("student__usn", "drive__title")


@admin.register(InterviewRound)
class InterviewRoundAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "round_type",
        "scheduled_at",
        "result",
    )
    list_filter = ("round_type", "result")


@admin.register(PlacementOffer)
class PlacementOfferAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "offered_package_lpa",
        "offer_date",
        "accepted",
    )
    list_filter = ("accepted",)