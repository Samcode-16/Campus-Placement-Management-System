from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from accounts.views import home_view, dashboard_view
from accounts import admin_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_view, name="home"),
    path("admin-dashboard/", dashboard_view, name="admin_dashboard"),

    # Student Management (Phase 3)
    path("admin-dashboard/students/", admin_views.admin_student_list_view, name="admin_student_list"),
    path("admin-dashboard/students/<int:pk>/", admin_views.admin_student_detail_view, name="admin_student_detail"),
    path("admin-dashboard/students/<int:pk>/edit/", admin_views.admin_student_edit_view, name="admin_student_edit"),
    path("admin-dashboard/students/<int:pk>/toggle-status/", admin_views.admin_student_toggle_status_view, name="admin_student_toggle_status"),
    path("admin-dashboard/students/<int:pk>/resume/", admin_views.admin_student_resume_view, name="admin_student_resume"),

    # Company Management (Phase 3)
    path("admin-dashboard/companies/", admin_views.admin_company_list_view, name="admin_company_list"),
    path("admin-dashboard/companies/create/", admin_views.admin_company_create_view, name="admin_company_create"),
    path("admin-dashboard/companies/<int:pk>/", admin_views.admin_company_detail_view, name="admin_company_detail"),
    path("admin-dashboard/companies/<int:pk>/edit/", admin_views.admin_company_edit_view, name="admin_company_edit"),
    path("admin-dashboard/companies/<int:pk>/delete/", admin_views.admin_company_delete_view, name="admin_company_delete"),

    # Placement Drive Management (Phase 4)
    path("admin-dashboard/drives/", admin_views.admin_drive_list_view, name="admin_drive_list"),
    path("admin-dashboard/drives/create/", admin_views.admin_drive_create_view, name="admin_drive_create"),
    path("admin-dashboard/drives/<int:pk>/", admin_views.admin_drive_detail_view, name="admin_drive_detail"),
    path("admin-dashboard/drives/<int:pk>/edit/", admin_views.admin_drive_edit_view, name="admin_drive_edit"),
    path("admin-dashboard/drives/<int:pk>/delete/", admin_views.admin_drive_delete_view, name="admin_drive_delete"),
    path("admin-dashboard/drives/<int:pk>/status/", admin_views.admin_drive_status_view, name="admin_drive_status"),

    # Application Management (Phase 4)
    path("admin-dashboard/applications/", admin_views.admin_application_list_view, name="admin_application_list"),
    path("admin-dashboard/applications/<int:pk>/", admin_views.admin_application_detail_view, name="admin_application_detail"),
    path("admin-dashboard/applications/<int:pk>/status/", admin_views.admin_application_status_view, name="admin_application_status"),
    path("admin-dashboard/applications/<int:pk>/resume/", admin_views.admin_application_resume_view, name="admin_application_resume"),

    path("accounts/", include("accounts.urls")),
    path("recruitment/", include("recruitment.urls")),
    path("training/", include("training.urls")),

    # Legal pages (public)
    path("privacy/", TemplateView.as_view(template_name="legal/privacy.html"), name="privacy"),
    path("terms/", TemplateView.as_view(template_name="legal/terms.html"), name="terms"),
    path("dpdp-notice/", TemplateView.as_view(template_name="legal/dpdp.html"), name="dpdp"),
]

# Serve uploaded resumes during development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
