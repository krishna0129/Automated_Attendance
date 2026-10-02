from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("not_authorised", views.not_authorised, name="not-authorised"),
    # Kiosk
    path("mark_your_attendance", views.mark_your_attendance, name="mark-your-attendance"),
    path("mark_your_attendance_out", views.mark_your_attendance_out, name="mark-your-attendance-out"),
    # Administration
    path("add_photos/", views.add_photos, name="add-photos"),
    path("train/", views.train, name="train"),
    # Reports
    path("view_attendance_home", views.view_attendance_home, name="view-attendance-home"),
    path("view_attendance_date", views.view_attendance_date, name="view-attendance-date"),
    path("view_attendance_employee", views.view_attendance_employee, name="view-attendance-employee"),
    path("view_my_attendance", views.view_my_attendance_employee_login, name="view-my-attendance-employee-login"),
]
