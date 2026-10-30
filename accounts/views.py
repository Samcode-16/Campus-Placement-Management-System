from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.decorators import is_staff_member, is_student, staff_required, student_required
from accounts.forms import StudentProfileForm, StudentRegistrationForm
from accounts.models import StudentProfile
from recruitment.models import (
    Application, Company, InterviewRound, PlacementDrive, PlacementOffer,
)
from training.models import TrainingProgram


def home_view(request):
    """Public landing page. Logged-in users are sent to their own dashboard."""
    if is_staff_member(request.user):
        return redirect("accounts:staff_dashboard")
    if is_student(request.user):
        return redirect("accounts:student_dashboard")

    open_drives = PlacementDrive.objects.filter(
        status=PlacementDrive.Status.OPEN, application_deadline__gte=timezone.now()
    )
    context = {
        "stats": {
            "students": StudentProfile.objects.count(),
            "companies": Company.objects.count(),
            "open_drives": open_drives.count(),
            "offers": PlacementOffer.objects.count(),
        },
        "featured_drives": open_drives.select_related("company").order_by(
            "application_deadline"
        )[:4],
    }
    return render(request, "accounts/home.html", context)


class RoleLoginView(LoginView):
    """Login page for one role. Already-signed-in users go to their dashboard."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)


def register_view(request):
    if is_student(request.user):
        return redirect("accounts:student_dashboard")

    form = StudentRegistrationForm(request.POST or None)
    if not form.fields["department"].queryset.exists():
        messages.error(
            request,
            "Registration is not open yet: no departments have been set up. "
            "Please contact the placement office.",
        )
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Registration successful. Welcome to CPMS!")
        return redirect("accounts:student_dashboard")
    return render(request, "accounts/register.html", {"form": form})


@student_required
def student_dashboard_view(request):
    student = request.user.student_profile
    applications = (
        Application.objects.filter(student=student)
        .select_related("drive__company")
        .order_by("-applied_at")
    )
    applied_ids = set(applications.values_list("drive_id", flat=True))

    open_drives = [
        d for d in PlacementDrive.objects.select_related("company").prefetch_related(
            "eligible_departments"
        )
        if d.is_accepting_applications()
    ]
    eligible_open = [
        d for d in open_drives
        if d.id not in applied_ids and not d.eligibility_issues(student)
    ]

    context = {
        "student": student,
        "total_applications": applications.count(),
        "shortlisted": applications.filter(status=Application.Status.SHORTLISTED).count(),
        "selected": applications.filter(status=Application.Status.SELECTED).count(),
        "eligible_open_count": len(eligible_open),
        "eligible_open": eligible_open[:5],
        "recent_applications": applications[:5],
        "upcoming_rounds": InterviewRound.objects.filter(
            application__student=student,
            scheduled_at__gte=timezone.now(),
            result=InterviewRound.Result.PENDING,
        ).select_related("application__drive__company")[:5],
    }
    return render(request, "accounts/student_dashboard.html", context)


@student_required
def student_profile_view(request):
    student = request.user.student_profile
    form = StudentProfileForm(
        request.POST or None, request.FILES or None, instance=student
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:student_profile")
    return render(
        request, "accounts/student_profile.html", {"student": student, "form": form}
    )


@staff_required
def dashboard_view(request):
    """Placement officer dashboard."""
    context = {
        "total_students": StudentProfile.objects.count(),
        "total_users": User.objects.count(),
        "total_companies": Company.objects.count(),
        "open_drives": PlacementDrive.objects.filter(
            status=PlacementDrive.Status.OPEN
        ).count(),
        "total_applications": Application.objects.count(),
        "pending_applications": Application.objects.filter(
            status=Application.Status.APPLIED
        ).count(),
        "total_training_programs": TrainingProgram.objects.count(),
        "recent_drives": PlacementDrive.objects.select_related(
            "company"
        ).order_by("-created_at")[:5],
    }
    return render(request, "dashboard.html", context)
