from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import StaffLoginForm, StudentLoginForm

app_name = "accounts"

urlpatterns = [
    # Student side
    path(
        "login/",
        views.RoleLoginView.as_view(
            template_name="accounts/student_login.html",
            authentication_form=StudentLoginForm,
            next_page=reverse_lazy("accounts:student_dashboard"),
        ),
        name="login",
    ),
    path("register/", views.register_view, name="register"),
    path("student/", views.student_dashboard_view, name="student_dashboard"),
    path("student/profile/", views.student_profile_view, name="student_profile"),

    # Placement officer side
    path(
        "staff-login/",
        views.RoleLoginView.as_view(
            template_name="accounts/staff_login.html",
            authentication_form=StaffLoginForm,
            next_page=reverse_lazy("accounts:staff_dashboard"),
        ),
        name="staff_login",
    ),
    path("staff/", views.dashboard_view, name="staff_dashboard"),

    # Shared
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
]
