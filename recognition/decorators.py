from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def is_admin(user) -> bool:
    return user.is_authenticated and user.is_staff


def admin_required(view):
    """Allow only staff users; send everyone else to the not-authorised page."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            return redirect("not-authorised")
        return view(request, *args, **kwargs)

    return wrapper


def student_required(view):
    """Allow only non-staff users (administrators have no attendance of their own)."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if is_admin(request.user):
            return redirect("not-authorised")
        return view(request, *args, **kwargs)

    return wrapper
