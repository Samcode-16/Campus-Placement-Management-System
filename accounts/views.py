from django.contrib import messages
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import User
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

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
            if is_staff_member(request.user):
                return redirect("accounts:staff_dashboard")
            if is_student(request.user):
                return redirect("accounts:student_dashboard")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        messages.success(
            self.request,
            f"Welcome back, {user.get_full_name() or user.username}!",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request,
            "Invalid username or password. Please try again.",
        )
        return super().form_invalid(form)

    def get_success_url(self):
        redirect_to = self.request.POST.get(
            self.redirect_field_name,
            self.request.GET.get(self.redirect_field_name, ""),
        )
        if redirect_to and url_has_allowed_host_and_scheme(
            redirect_to, {self.request.get_host()}
        ):
            if not is_staff_member(self.request.user) and (
                "admin" in redirect_to or "manage" in redirect_to
            ):
                messages.error(
                    self.request,
                    "Access denied. Administrator privileges are required to view that page.",
                )
                return reverse("accounts:student_dashboard")
            return redirect_to

        if self.next_page:
            from django.shortcuts import resolve_url
            return resolve_url(self.next_page)

        if is_staff_member(self.request.user):
            return reverse("admin_dashboard")
        return reverse("accounts:student_dashboard")


class CustomLogoutView(View):
    """Logs the user out, adds a flash confirmation message, and redirects to home."""

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            auth_logout(request)
            messages.success(request, "You have been successfully logged out.")
        return redirect("home")

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


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
    """Frontend Administrator Dashboard with statistics, analytics charts, and recent activity streams."""
    # 1. Dashboard Statistics (8 key database-backed metrics)
    total_students = StudentProfile.objects.count()
    total_companies = Company.objects.count()
    total_drives = PlacementDrive.objects.count()
    open_drives = PlacementDrive.objects.filter(status=PlacementDrive.Status.OPEN).count()
    total_applications = Application.objects.count()
    pending_applications = Application.objects.filter(status=Application.Status.APPLIED).count()
    shortlisted_count = Application.objects.filter(status=Application.Status.SHORTLISTED).count()
    selected_count = Application.objects.filter(status=Application.Status.SELECTED).count()
    total_training_programs = TrainingProgram.objects.count()

    # Derived student selection numbers
    selected_students = (
        StudentProfile.objects.filter(applications__status=Application.Status.SELECTED)
        .distinct()
        .count()
    )
    non_selected_students = max(0, total_students - selected_students)
    selection_rate = (
        round((selected_students / total_students * 100), 1)
        if total_students > 0
        else 0
    )
    non_selection_rate = (
        round(100 - selection_rate, 1)
        if total_students > 0
        else 0
    )

    # 2. Visualizations
    # 2a. Applications by status
    status_counts = dict(
        Application.objects.values("status")
        .annotate(count=Count("id"))
        .values_list("status", "count")
    )
    status_colors = {
        Application.Status.APPLIED: "#2850a0",      # Navy/Blue
        Application.Status.SHORTLISTED: "#0f766e",  # Teal
        Application.Status.SELECTED: "#146c43",     # Green (Success)
        Application.Status.REJECTED: "#b42318",     # Red (Danger)
        Application.Status.WITHDRAWN: "#5b6b82",    # Slate/Gray
    }
    apps_by_status = []
    for val, label in Application.Status.choices:
        cnt = status_counts.get(val, 0)
        pct = round((cnt / total_applications * 100), 1) if total_applications > 0 else 0
        apps_by_status.append({
            "key": val,
            "label": label,
            "count": cnt,
            "percentage": pct,
            "color": status_colors.get(val, "#5b6b82"),
        })

    # 2b. Placement drives by category (IT, CORE, BANKING)
    cat_counts = dict(
        PlacementDrive.objects.values("category")
        .annotate(count=Count("id"))
        .values_list("category", "count")
    )
    cat_colors = {
        PlacementDrive.Category.IT: "#0f766e",       # Teal
        PlacementDrive.Category.CORE: "#14284b",     # Navy
        PlacementDrive.Category.BANKING: "#b45309",  # Amber
    }
    drives_by_category = []
    for val, label in PlacementDrive.Category.choices:
        cnt = cat_counts.get(val, 0)
        pct = round((cnt / total_drives * 100), 1) if total_drives > 0 else 0
        drives_by_category.append({
            "key": val,
            "label": label,
            "count": cnt,
            "percentage": pct,
            "color": cat_colors.get(val, "#0f766e"),
        })

    # 2c. Monthly application trends
    monthly_raw = list(
        Application.objects.annotate(month=TruncMonth("applied_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    monthly_trends = []
    max_month_count = max([m["count"] for m in monthly_raw], default=1) or 1
    for m in monthly_raw:
        if m["month"]:
            cnt = m["count"]
            monthly_trends.append({
                "label": m["month"].strftime("%b %Y"),
                "short_label": m["month"].strftime("%b"),
                "count": cnt,
                "percentage": round((cnt / max_month_count * 100), 1),
            })

    # 3. Recent Activities (5 streams)
    recent_students = (
        StudentProfile.objects.select_related("user", "department")
        .order_by("-created_at")[:5]
    )
    recent_companies = (
        Company.objects.annotate(drives_count=Count("drives"))
        .order_by("-created_at")[:5]
    )
    recent_drives = (
        PlacementDrive.objects.select_related("company")
        .order_by("-created_at")[:5]
    )
    latest_applications = (
        Application.objects.select_related(
            "student__user", "student__department", "drive__company"
        )
        .order_by("-applied_at")[:5]
    )
    recent_status_updates = (
        Application.objects.exclude(status=Application.Status.APPLIED)
        .select_related(
            "student__user", "student__department", "drive__company"
        )
        .order_by("-applied_at")[:5]
    )

    context = {
        # 8 key statistics
        "total_students": total_students,
        "total_companies": total_companies,
        "total_drives": total_drives,
        "open_drives": open_drives,
        "total_applications": total_applications,
        "pending_applications": pending_applications,
        "shortlisted_count": shortlisted_count,
        "selected_count": selected_count,
        "total_training_programs": total_training_programs,

        # Selected vs Non-selected
        "selected_students": selected_students,
        "non_selected_students": non_selected_students,
        "selection_rate": selection_rate,
        "non_selection_rate": non_selection_rate,

        # Visualizations
        "apps_by_status": apps_by_status,
        "drives_by_category": drives_by_category,
        "monthly_trends": monthly_trends,

        # Recent activities
        "recent_students": recent_students,
        "recent_companies": recent_companies,
        "recent_drives": recent_drives,
        "latest_applications": latest_applications,
        "recent_status_updates": recent_status_updates,
    }
    return render(request, "dashboard.html", context)
