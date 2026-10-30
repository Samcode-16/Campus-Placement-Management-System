from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.decorators import is_staff_member, is_student, staff_required, student_required
from .forms import ApplicationForm
from .models import Application, PlacementDrive


@login_required
def placement_drives_view(request):
    drives = PlacementDrive.objects.select_related("company").all()

    category = request.GET.get("category")
    if category in ["IT", "CORE", "BANKING"]:
        drives = drives.filter(category=category)

    applied_ids = set()
    if is_student(request.user):
        # Students never see drafts
        drives = drives.exclude(status=PlacementDrive.Status.DRAFT)
        applied_ids = set(
            request.user.student_profile.applications.values_list("drive_id", flat=True)
        )

    drives = list(drives)
    for drive in drives:
        drive.already_applied = drive.id in applied_ids
        drive.can_apply = drive.is_accepting_applications() and not drive.already_applied

    context = {"drives": drives, "selected_category": category or ""}
    return render(request, "recruitment/placement_drives.html", context)


@login_required
def drive_detail_view(request, pk):
    drive = get_object_or_404(
        PlacementDrive.objects.select_related("company").prefetch_related(
            "eligible_departments"
        ),
        pk=pk,
    )
    context = {"drive": drive}

    if is_student(request.user):
        if drive.status == PlacementDrive.Status.DRAFT:
            return redirect("recruitment:placement_drives")
        student = request.user.student_profile
        application = Application.objects.filter(student=student, drive=drive).first()
        issues = drive.eligibility_issues(student)
        context.update(
            application=application,
            issues=issues,
            can_apply=(
                drive.is_accepting_applications()
                and not issues
                and (application is None or application.status == Application.Status.WITHDRAWN)
            ),
        )
    return render(request, "recruitment/drive_detail.html", context)


@student_required
def apply_view(request, pk):
    drive = get_object_or_404(
        PlacementDrive.objects.select_related("company"), pk=pk
    )
    student = request.user.student_profile
    existing = Application.objects.filter(student=student, drive=drive).first()

    # Server-side checks: never rely on the button being hidden in the template
    problem = None
    if drive.status == PlacementDrive.Status.DRAFT:
        return redirect("recruitment:placement_drives")
    if not drive.is_accepting_applications():
        problem = "This drive is not accepting applications."
    elif existing and existing.status != Application.Status.WITHDRAWN:
        problem = "You have already applied to this drive."
    else:
        issues = drive.eligibility_issues(student)
        if issues:
            problem = "You are not eligible: " + " ".join(issues)
    if problem:
        messages.error(request, problem)
        return redirect("recruitment:drive_detail", pk=drive.pk)

    form = ApplicationForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        resume = form.cleaned_data["resume"] or student.resume
        if not resume:
            form.add_error("resume", "Upload a resume, or add one to your profile first.")
        else:
            with transaction.atomic():
                if existing:  # re-applying after a withdrawal
                    existing.status = Application.Status.APPLIED
                    existing.resume = resume
                    existing.save()
                else:
                    Application.objects.create(student=student, drive=drive, resume=resume)
            messages.success(request, f"Application submitted to {drive.company.name}.")
            return redirect("recruitment:my_applications")

    return render(
        request,
        "recruitment/apply.html",
        {"drive": drive, "form": form, "student": student},
    )


@student_required
def my_applications_view(request):
    applications = (
        Application.objects.filter(student=request.user.student_profile)
        .select_related("drive__company", "offer")
        .prefetch_related("interview_rounds")
    )
    return render(
        request, "recruitment/my_applications.html", {"applications": applications}
    )


@student_required
@require_POST
def withdraw_view(request, pk):
    application = get_object_or_404(
        Application, pk=pk, student=request.user.student_profile
    )
    if application.status in (Application.Status.APPLIED, Application.Status.SHORTLISTED):
        application.status = Application.Status.WITHDRAWN
        application.save(update_fields=["status"])
        messages.success(request, "Application withdrawn.")
    else:
        messages.error(request, "This application can no longer be withdrawn.")
    return redirect("recruitment:my_applications")


@staff_required
def manage_applications_view(request):
    applications = Application.objects.select_related(
        "student__user", "student__department", "drive__company"
    )

    status = request.GET.get("status", "")
    drive_id = request.GET.get("drive", "")
    if status in Application.Status.values:
        applications = applications.filter(status=status)
    if drive_id.isdigit():
        applications = applications.filter(drive_id=drive_id)

    context = {
        "applications": applications,
        "status_choices": Application.Status.choices,
        "reviewable_choices": [
            c for c in Application.Status.choices
            if c[0] != Application.Status.WITHDRAWN
        ],
        "drives": PlacementDrive.objects.select_related("company"),
        "selected_status": status,
        "selected_drive": drive_id,
    }
    return render(request, "recruitment/manage_applications.html", context)


@staff_required
@require_POST
def update_status_view(request, pk):
    application = get_object_or_404(Application, pk=pk)
    new_status = request.POST.get("status")
    allowed = set(Application.Status.values) - {Application.Status.WITHDRAWN}
    if new_status in allowed and application.status != Application.Status.WITHDRAWN:
        application.status = new_status
        application.save(update_fields=["status"])
        messages.success(
            request,
            f"{application.student.usn}: status set to {application.get_status_display()}.",
        )
    else:
        messages.error(request, "Invalid status change.")
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        return redirect(next_url)
    return redirect("recruitment:manage_applications")
