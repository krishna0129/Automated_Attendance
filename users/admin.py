from django.contrib import admin

from .models import Present, Time


@admin.register(Present)
class PresentAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "present")
    list_filter = ("present", "date")
    search_fields = ("user__username",)


@admin.register(Time)
class TimeAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "time", "out")
    list_filter = ("out", "date")
    search_fields = ("user__username",)
