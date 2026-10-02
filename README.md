# Attendance System Using Face Recognition

A Django web app that marks student attendance by recognising faces from a
webcam. Administrators register students, capture their photos and train a
classifier; students check in and out at a kiosk and can view their own
attendance history.

## Requirements

- Python **3.10 or newer**
- A webcam on the machine that runs the server (the camera window opens there)
- Build tools for `dlib`: CMake and a C++ compiler
  (`sudo apt install cmake build-essential` on Debian/Ubuntu,
  Visual Studio Build Tools on Windows)

## Quick start (SQLite, photos on disk)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # dlib compiles from source; this takes a while

cp .env.example .env               # optional, defaults work for local use
python manage.py migrate
python manage.py createsuperuser   # the administrator account
python manage.py runserver
```

Open http://127.0.0.1:8000, log in as the administrator, then:

1. **Register student**: create a login for each student.
2. **Add photos**: enter the username; the camera captures face samples.
3. **Train model**: fit the classifier on every stored photo
   (needs at least two students).
4. On the home page, **Check in** / **Check out** opens the camera. Press
   **Q** in the camera window when everyone has been recognised.

Administrators are users with *staff status* (`createsuperuser` sets it).
Everyone else is treated as a student.

## Using PostgreSQL

All data, including attendance and (optionally) the face photos, can live
in a dedicated PostgreSQL server. Set `DATABASE_URL`:

```bash
docker compose up -d   # optional: starts a local Postgres from docker-compose.yml
export DATABASE_URL=postgres://attendance:attendance@localhost:5432/attendance
python manage.py migrate
python manage.py createsuperuser
```

To move existing data from the bundled SQLite file into Postgres:

```bash
# 1. Export from SQLite (DATABASE_URL unset)
python manage.py dumpdata --natural-foreign --natural-primary \
    -e contenttypes -e auth.permission -e admin.logentry -e sessions -o data.json
# 2. Load into Postgres
export DATABASE_URL=postgres://...
python manage.py migrate
python manage.py loaddata data.json
```

## Where face photos are stored

`FACE_IMAGE_STORAGE` selects the backend:

| Value                  | Location                                                 |
|------------------------|----------------------------------------------------------|
| `filesystem` (default) | `face_recognition_data/training_dataset/<username>/*.jpg` |
| `database`             | `FaceImage` table in the database from `DATABASE_URL`     |

With `database` storage and PostgreSQL, the photos sit next to the
attendance data, so they are backed up together and any server pointed at
the database can train the model.

Copy existing photos between backends (usernames must already exist):

```bash
python manage.py copy_face_images --from filesystem --to database
# add --replace to overwrite a student's photos already in the target
```

Then set `FACE_IMAGE_STORAGE=database` and re-train.

The trained classifier is saved to `face_recognition_data/classifier.joblib`
(or `FACE_DATA_DIR`). Re-create it at any time from **Train model**.

## Configuration

Every setting comes from environment variables or a `.env` file; see
[`.env.example`](.env.example). The most important ones:

| Variable                 | Default             | Purpose                                     |
|--------------------------|---------------------|---------------------------------------------|
| `DJANGO_DEBUG`           | `true`              | Set `false` in production                   |
| `DJANGO_SECRET_KEY`      | dev-only key        | Required in production                      |
| `DJANGO_ALLOWED_HOSTS`   | `*` in debug        | Comma-separated host names                  |
| `DATABASE_URL`           | SQLite `db.sqlite3` | Any URL supported by `dj-database-url`      |
| `FACE_IMAGE_STORAGE`     | `filesystem`        | `filesystem` or `database`                  |
| `FACE_DATA_DIR`          | `face_recognition_data/` | Classifier and on-disk photos          |
| `FACE_MATCH_THRESHOLD`   | `0.7`               | Minimum classifier confidence for a match   |
| `FACE_MIN_HITS`          | `3`                 | Frames a face must be matched in to count   |
| `FACE_SAMPLES_PER_USER`  | `300`               | Photos captured by **Add photos**           |
| `FACE_CAMERA_INDEX`      | `0`                 | OpenCV camera index                         |

## Project layout

```
attendance_system_facial_recognition/   Django project: settings, root URLs
recognition/
    views.py           HTTP views (thin; delegate to the modules below)
    attendance.py      Recording check-ins/outs, hours and break calculations, stats
    face_engine.py     Camera loop, face detection, recognition and training
    face_storage.py    Face photo storage backends (filesystem / database)
    charts.py          Matplotlib charts rendered to inline images
    forms.py           Report and photo-capture forms
    decorators.py      admin_required / student_required
    models.py          FaceImage (photos stored in the database)
    management/commands/copy_face_images.py
users/
    models.py          Present (per-day status) and Time (check-in/out events)
    views.py           Student registration
```

## Tests

```bash
python manage.py test
```

The tests mock the camera, so they run without a webcam.
