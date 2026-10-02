"""
Django settings for the attendance system.

Configuration is read from environment variables (optionally via a `.env`
file in the project root). See `.env.example` for every supported variable.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", True)

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    # Development-only fallback. Always set DJANGO_SECRET_KEY in production.
    "dev-insecure-4!of@+5)(cu6!@c&21m644*%n5)h(9h6shzgg5ka%005e=04qu",
)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "users.apps.UsersConfig",
    "recognition.apps.RecognitionConfig",
    "crispy_forms",
    "crispy_bootstrap4",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "attendance_system_facial_recognition.urls"
WSGI_APPLICATION = "attendance_system_facial_recognition.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
#
# Defaults to the bundled SQLite file. Point DATABASE_URL at PostgreSQL to use
# a dedicated server, e.g.
#   DATABASE_URL=postgres://attendance:secret@localhost:5432/attendance
# ---------------------------------------------------------------------------

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=int(os.environ.get("DATABASE_CONN_MAX_AGE", "60")),
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# I18N / time
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
# Attendance timestamps are stored as naive local times.
USE_TZ = False

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap4"
CRISPY_TEMPLATE_PACK = "bootstrap4"

# ---------------------------------------------------------------------------
# Face recognition
# ---------------------------------------------------------------------------

# Where the trained classifier and (for the filesystem backend) photos live.
FACE_DATA_DIR = Path(os.environ.get("FACE_DATA_DIR", BASE_DIR / "face_recognition_data"))

# Where captured face photos are stored:
#   "filesystem" - JPEG files under FACE_DATA_DIR/training_dataset/<username>/
#   "database"   - rows in the FaceImage table of the configured database
#                  (use with PostgreSQL for a dedicated, shareable store)
FACE_IMAGE_STORAGE = os.environ.get("FACE_IMAGE_STORAGE", "filesystem").strip().lower()

FACE_RECOGNITION = {
    # Webcam index passed to OpenCV.
    "CAMERA_INDEX": int(os.environ.get("FACE_CAMERA_INDEX", "0")),
    # Number of face samples captured per student by "Add photos".
    "SAMPLES_PER_USER": int(os.environ.get("FACE_SAMPLES_PER_USER", "300")),
    # Minimum classifier probability to accept a match.
    "MATCH_THRESHOLD": float(os.environ.get("FACE_MATCH_THRESHOLD", "0.7")),
    # Maximum face-encoding distance to the matched student's training photos.
    # Faces further than this are treated as strangers (0.6 is the
    # face_recognition library's standard tolerance; lower is stricter).
    "MAX_DISTANCE": float(os.environ.get("FACE_MAX_DISTANCE", "0.6")),
    # Frames a person must be recognised in before they are marked.
    "MIN_HITS": int(os.environ.get("FACE_MIN_HITS", "3")),
}
