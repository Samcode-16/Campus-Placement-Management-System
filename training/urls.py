
from django.urls import path
from .views import training_programs_view

app_name = "training"

urlpatterns = [
    path("", training_programs_view, name="training_programs"),
]
