from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from accounts.views import home_view


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_view, name="home"),
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
