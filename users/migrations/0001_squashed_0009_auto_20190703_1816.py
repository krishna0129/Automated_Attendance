# Squashes the 2019 history (an "Attendance" model that was created, altered
# and finally replaced by Present/Time). One of those steps converted a
# TimeField to a DateTimeField, which PostgreSQL cannot do, so a fresh
# PostgreSQL database could not be migrated. Existing databases that already
# applied 0001-0009 treat this migration as applied via `replaces`.

import datetime

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    replaces = [
        ("users", "0001_initial"),
        ("users", "0002_auto_20190628_0514"),
        ("users", "0003_auto_20190628_1110"),
        ("users", "0004_auto_20190628_1114"),
        ("users", "0005_auto_20190628_1155"),
        ("users", "0006_auto_20190701_1522"),
        ("users", "0007_auto_20190701_1523"),
        ("users", "0008_auto_20190701_1525"),
        ("users", "0009_auto_20190703_1816"),
    ]

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Present",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(default=datetime.date.today)),
                ("present", models.BooleanField(default=False)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Time",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(default=datetime.date.today)),
                ("time", models.DateTimeField(blank=True, null=True)),
                ("out", models.BooleanField(default=False)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
