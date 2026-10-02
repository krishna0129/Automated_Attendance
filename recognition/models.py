from django.contrib.auth.models import User
from django.db import models


class FaceImage(models.Model):
    """A captured face sample, used when FACE_IMAGE_STORAGE = "database"."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="face_images")
    image = models.BinaryField(help_text="JPEG-encoded, aligned face crop.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user_id", "id"]

    def __str__(self):
        return f"Face image #{self.pk} of {self.user.username}"
