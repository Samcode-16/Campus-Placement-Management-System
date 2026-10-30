from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, resolve_url


def is_student(user):
    return (
        user.is_authenticated
        and not user.is_staff
        and hasattr(user, "student_profile")
    )


def is_staff_member(user):
    return user.is_authenticated and user.is_staff


def _role_required(check, login_url, denied_message):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(
                    request.get_full_path(), resolve_url(login_url)
                )
            if not check(request.user):
                messages.error(request, denied_message)
                return redirect("home")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


student_required = _role_required(
    is_student,
    "accounts:login",
    "That page is only for students.",
)

staff_required = _role_required(
    is_staff_member,
    "accounts:staff_login",
    "That page is only for placement officers.",
)
