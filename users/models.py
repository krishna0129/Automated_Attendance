import datetime

from django.contrib.auth.models import User
from django.db import models


class Present(models.Model):
    """One row per student per day: whether they were marked present."""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=datetime.date.today)
    present = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} {self.date} {'present' if self.present else 'absent'}"


class Time(models.Model):
    """A single check-in (out=False) or check-out (out=True) event."""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=datetime.date.today)
    time = models.DateTimeField(null=True, blank=True)
    out = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} {'out' if self.out else 'in'} {self.time}"
