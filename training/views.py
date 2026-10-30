
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import TrainingProgram


@login_required
def training_programs_view(request):
    programs = TrainingProgram.objects.all()

    mode = request.GET.get("mode", "")
    status = request.GET.get("status", "")

    valid_modes = [
        choice[0] for choice in TrainingProgram.Mode.choices
    ]
    valid_statuses = [
        choice[0] for choice in TrainingProgram.Status.choices
    ]

    if mode in valid_modes:
        programs = programs.filter(mode=mode)

    if status in valid_statuses:
        programs = programs.filter(status=status)

    context = {
    "programs": programs,
    "selected_mode": mode,
    "selected_status": status,
    "mode_choices": TrainingProgram.Mode.choices,
    "status_choices": TrainingProgram.Status.choices,
    }

    return render(
        request,
        "training/training_programs.html",
        context
    )
