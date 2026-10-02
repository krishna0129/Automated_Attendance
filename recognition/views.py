import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from users.models import Present, Time

from . import attendance, charts, face_engine
from .decorators import admin_required, is_admin, student_required
from .face_storage import get_face_store
from .forms import DateForm, DateRangeForm, UsernameAndDateRangeForm, UsernameForm


def home(request):
    return render(request, "recognition/home.html")


@login_required
def dashboard(request):
    template = "admin_dashboard.html" if is_admin(request.user) else "employee_dashboard.html"
    return render(request, f"recognition/{template}")


@login_required
def not_authorised(request):
    return render(request, "recognition/not_authorised.html")


# ---------------------------------------------------------------------------
# Kiosk: marking attendance
# ---------------------------------------------------------------------------


def _mark_attendance(request, *, title, record, verb):
    try:
        recognised = face_engine.recognise_faces(title)
    except face_engine.FaceEngineError as exc:
        messages.error(request, str(exc))
        return redirect("home")

    marked = record(recognised)
    if marked:
        messages.success(request, f"Checked {verb}: {', '.join(marked)}.")
    else:
        messages.warning(request, "No one was recognised. Please try again.")
    return redirect("home")


@require_POST
def mark_your_attendance(request):
    return _mark_attendance(request, title="Mark attendance - In", record=attendance.mark_in, verb="in")


@require_POST
def mark_your_attendance_out(request):
    return _mark_attendance(request, title="Mark attendance - Out", record=attendance.mark_out, verb="out")


# ---------------------------------------------------------------------------
# Administration
# ---------------------------------------------------------------------------


@admin_required
def add_photos(request):
    form = UsernameForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            saved = face_engine.capture_samples(form.user, get_face_store())
        except face_engine.FaceEngineError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Saved {saved} photos of {form.user.username}. Train the model to use them.")
        return redirect("add-photos")
    return render(request, "recognition/add_photos.html", {"form": form})


@admin_required
def train(request):
    result = None
    if request.method == "POST":
        try:
            result = face_engine.train_classifier(get_face_store())
        except face_engine.FaceEngineError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Training complete.")
    return render(request, "recognition/train.html", {"result": result})


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _hours_by_date_chart(rows):
    return charts.bar_chart(
        [row.date.strftime("%d %b") for row in rows],
        [row.hours_value for row in rows],
        xlabel="Date",
        ylabel="Hours",
    )


def _hours_by_student_chart(rows):
    return charts.bar_chart(
        [row.user.username for row in rows],
        [row.hours_value for row in rows],
        xlabel="Student",
        ylabel="Hours",
    )


def _weekly_chart(monday):
    counts = attendance.weekly_present_counts(monday)
    return charts.line_chart(
        [day.strftime("%a %d %b") for day, _ in counts],
        [n for _, n in counts],
        xlabel="Date",
        ylabel="Students present",
    )


@admin_required
def view_attendance_home(request):
    today = datetime.date.today()
    this_monday = attendance.monday_of(today)
    total = attendance.students().count()
    present = attendance.present_count(today)
    return render(
        request,
        "recognition/view_attendance_home.html",
        {
            "total_num_of_emp": total,
            "emp_present_today": present,
            "emp_absent_today": max(total - present, 0),
            "this_week_chart": _weekly_chart(this_monday),
            "last_week_chart": _weekly_chart(this_monday - datetime.timedelta(days=7)),
        },
    )


def _range_report(request, form, user, template):
    """Render the per-day report of ``user`` for the form's date range."""
    span = {"date__gte": form.cleaned_data["date_from"], "date__lte": form.cleaned_data["date_to"]}
    rows = attendance.daily_attendance(
        Present.objects.filter(user=user, **span).order_by("-date"),
        Time.objects.filter(user=user, **span),
    )
    if not rows:
        messages.warning(request, "No records for the selected duration.")
    context = {"form": form, "qs": rows, "chart": _hours_by_date_chart(rows) if rows else None}
    return render(request, template, context)


@admin_required
def view_attendance_date(request):
    form = DateForm(request.POST or None)
    rows, chart = None, None
    if request.method == "POST" and form.is_valid():
        day = form.cleaned_data["date"]
        rows = attendance.daily_attendance(
            Present.objects.filter(date=day).order_by("user__username"),
            Time.objects.filter(date=day),
        )
        if rows:
            chart = _hours_by_student_chart(rows)
        else:
            messages.warning(request, "No records for the selected date.")
    return render(request, "recognition/view_attendance_date.html", {"form": form, "qs": rows, "chart": chart})


@admin_required
def view_attendance_employee(request):
    form = UsernameAndDateRangeForm(request.POST or None)
    template = "recognition/view_attendance_employee.html"
    if request.method == "POST" and form.is_valid():
        return _range_report(request, form, form.user, template)
    return render(request, template, {"form": form})


@student_required
def view_my_attendance_employee_login(request):
    form = DateRangeForm(request.POST or None)
    template = "recognition/view_my_attendance_employee_login.html"
    if request.method == "POST" and form.is_valid():
        return _range_report(request, form, request.user, template)
    return render(request, template, {"form": form})
