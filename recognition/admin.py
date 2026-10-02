from django.contrib import admin

from .models import FaceImage


@admin.register(FaceImage)
class FaceImageAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at")
    list_filter = ("user",)
    exclude = ("image",)
