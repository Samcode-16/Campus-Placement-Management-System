from django.urls import path
from . import views

app_name = "recruitment"

urlpatterns = [
    path("", views.placement_drives_view, name="placement_drives"),
    path("<int:pk>/", views.drive_detail_view, name="drive_detail"),
    path("<int:pk>/apply/", views.apply_view, name="apply"),

    # Student
    path("my-applications/", views.my_applications_view, name="my_applications"),
    path("applications/<int:pk>/withdraw/", views.withdraw_view, name="withdraw"),

    # Placement officer
    path("manage/", views.manage_applications_view, name="manage_applications"),
    path("manage/<int:pk>/status/", views.update_status_view, name="update_status"),
]
