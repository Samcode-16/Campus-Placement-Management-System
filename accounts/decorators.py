from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, resolve_url


def is_admin(user):
    """Returns True if the user has administrator / staff access."""
    if not (user and user.is_authenticated):
        return False
    return (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name__in=["Administrator", "Placement Officers"]).exists()
    )


def is_staff_member(user):
    """Alias for is_admin for backward compatibility."""
    return is_admin(user)


def is_student(user):
    """Returns True if user is an authenticated student (has student profile and no admin status)."""
    if not (user and user.is_authenticated):
        return False
    if is_admin(user):
        return False
    return hasattr(user, "student_profile")


def student_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in to access this page.")
            return redirect_to_login(
                request.get_full_path(), resolve_url("accounts:login")
            )
        if not is_student(request.user):
            messages.error(request, "That page is only for students.")
            if is_staff_member(request.user):
                return redirect("accounts:staff_dashboard")
            return redirect("home")
        return view(request, *args, **kwargs)

    return wrapper


def staff_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(
                request, "Please log in with an administrator account to access this page."
            )
            return redirect_to_login(
                request.get_full_path(), resolve_url("accounts:staff_login")
            )
        if not is_staff_member(request.user):
            messages.error(
                request,
                "Access denied. You do not have administrator permissions to view this page.",
            )
            if is_student(request.user):
                return redirect("accounts:student_dashboard")
            return redirect("home")
        return view(request, *args, **kwargs)

    return wrapper


admin_required = staff_required
