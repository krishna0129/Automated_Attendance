import datetime
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import Present, Time

from . import attendance, face_engine
from .face_storage import DatabaseFaceStore, FileSystemFaceStore, get_face_store
from .forms import DateRangeForm, UsernameAndDateRangeForm
from .models import FaceImage

DAY = datetime.date(2026, 9, 1)


def at(hour, minute=0, day=DAY):
    return datetime.datetime.combine(day, datetime.time(hour, minute))


class BreakHoursTests(TestCase):
    def events(self, *pairs):
        return [Time(time=at(*hm), out=out) for hm, out in pairs]

    def test_sums_gaps_between_out_and_next_in(self):
        events = self.events(((9, 0), False), ((12, 0), True), ((13, 0), False), ((17, 0), True))
        self.assertEqual(attendance.break_hours(events), 1.0)

    def test_single_in_out_has_no_break(self):
        self.assertEqual(attendance.break_hours(self.events(((9, 0), False), ((17, 0), True))), 0.0)

    def test_inconsistent_sequences_yield_zero(self):
        self.assertEqual(attendance.break_hours(self.events(((9, 0), True), ((10, 0), False))), 0.0)
        self.assertEqual(attendance.break_hours(self.events(((9, 0), False), ((10, 0), False))), 0.0)
        self.assertEqual(attendance.break_hours(self.events(((9, 0), False))), 0.0)
        self.assertEqual(attendance.break_hours([]), 0.0)

    def test_format_hours(self):
        self.assertEqual(attendance.format_hours(7.5), "7 hrs 30 mins")
        self.assertEqual(attendance.format_hours(0), "0 hrs 0 mins")
        self.assertEqual(attendance.format_hours(1.9999), "2 hrs 0 mins")


class AttendanceRecordingTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice")
        self.bob = User.objects.create_user("bob")
        User.objects.create_user("admin", is_staff=True)

    def test_mark_in_records_present_and_absent(self):
        marked = attendance.mark_in({"alice", "ghost"}, when=at(9))
        self.assertEqual(marked, ["alice"])
        self.assertTrue(Present.objects.get(user=self.alice, date=DAY).present)
        self.assertFalse(Present.objects.get(user=self.bob, date=DAY).present)
        self.assertFalse(Present.objects.filter(user__username="admin").exists())
        self.assertEqual(Time.objects.get(user=self.alice).out, False)

    def test_mark_in_upgrades_absent_row(self):
        attendance.mark_in(set(), when=at(9))
        attendance.mark_in({"bob"}, when=at(10))
        self.assertEqual(Present.objects.filter(user=self.bob, date=DAY).count(), 1)
        self.assertTrue(Present.objects.get(user=self.bob, date=DAY).present)

    def test_mark_in_tolerates_legacy_duplicate_rows(self):
        Present.objects.create(user=self.alice, date=DAY)
        Present.objects.create(user=self.alice, date=DAY)
        attendance.mark_in({"alice"}, when=at(9))
        self.assertTrue(all(p.present for p in Present.objects.filter(user=self.alice)))

    def test_daily_attendance(self):
        attendance.mark_in({"alice"}, when=at(9))
        attendance.mark_out({"alice"}, when=at(12))
        attendance.mark_in({"alice"}, when=at(13))
        attendance.mark_out({"alice"}, when=at(17, 30))

        rows = attendance.daily_attendance(Present.objects.filter(date=DAY), Time.objects.filter(date=DAY))
        by_user = {row.user.username: row for row in rows}

        alice = by_user["alice"]
        self.assertEqual((alice.time_in, alice.time_out), (at(9), at(17, 30)))
        self.assertEqual(alice.hours, "8 hrs 30 mins")
        self.assertEqual(alice.break_hours, "1 hrs 0 mins")
        self.assertFalse(by_user["bob"].present)
        self.assertIsNone(by_user["bob"].time_in)

    def test_weekly_counts_and_stats(self):
        monday = attendance.monday_of(datetime.date(2026, 9, 3))  # a Thursday
        self.assertEqual(monday, datetime.date(2026, 8, 31))
        attendance.mark_in({"alice", "bob"}, when=at(9, day=monday))
        attendance.mark_in({"alice"}, when=at(9, day=monday + datetime.timedelta(days=2)))

        counts = attendance.weekly_present_counts(monday)
        self.assertEqual([n for _, n in counts], [2, 0, 1, 0, 0])
        self.assertEqual(attendance.students().count(), 2)
        self.assertEqual(attendance.present_count(monday), 2)


class FaceStoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice")

    def exercise(self, store):
        store.save(self.user, b"one")
        store.save(self.user, b"two")
        self.assertEqual(store.count(self.user), 2)
        images = list(store.iter_images())
        self.assertEqual([(i.username, i.data) for i in images], [("alice", b"one"), ("alice", b"two")])
        store.delete(images[0].ref)
        self.assertEqual(store.count(self.user), 1)
        store.clear(self.user)
        self.assertEqual(store.count(self.user), 0)

    def test_filesystem_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.exercise(FileSystemFaceStore(Path(tmp)))

    def test_database_store(self):
        self.exercise(DatabaseFaceStore())

    def test_backend_selection(self):
        with override_settings(FACE_IMAGE_STORAGE="database"):
            self.assertIsInstance(get_face_store(), DatabaseFaceStore)
        with override_settings(FACE_IMAGE_STORAGE="filesystem"):
            self.assertIsInstance(get_face_store(), FileSystemFaceStore)

    def test_copy_command_moves_filesystem_images_into_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            fs = FileSystemFaceStore(Path(tmp) / "training_dataset")
            fs.save(self.user, b"jpeg")
            (Path(tmp) / "training_dataset" / "nobody").mkdir()
            (Path(tmp) / "training_dataset" / "nobody" / "1.jpg").write_bytes(b"x")
            out, err = StringIO(), StringIO()
            with override_settings(FACE_DATA_DIR=Path(tmp)):
                call_command("copy_face_images", "--from", "filesystem", "--to", "database", stdout=out, stderr=err)
        self.assertEqual(bytes(FaceImage.objects.get(user=self.user).image), b"jpeg")
        self.assertIn("Copied 1 images", out.getvalue())
        self.assertIn("nobody", err.getvalue())


class ClassifierPredictTests(TestCase):
    """Classifier.predict with the face encoder stubbed out."""

    def setUp(self):
        from sklearn.preprocessing import LabelEncoder
        from sklearn.svm import SVC
        import numpy as np

        rng = np.random.default_rng(0)
        self.alice_center, self.bob_center = np.zeros(128), np.full(128, 0.1)
        X = np.vstack([self.alice_center + rng.normal(0, 0.01, (10, 128)),
                       self.bob_center + rng.normal(0, 0.01, (10, 128))])
        labels = ["alice"] * 10 + ["bob"] * 10
        encoder = LabelEncoder().fit(labels)
        y = encoder.transform(labels)
        self.classifier = face_engine.Classifier(
            svc=SVC(kernel="linear", probability=True).fit(X, y), encoder=encoder, encodings=X, labels=y
        )

    def predict(self, encoding):
        with mock.patch.object(face_engine.face_recognition, "face_locations", return_value=[(0, 1, 1, 0)]), \
                mock.patch.object(face_engine.face_recognition, "face_encodings", return_value=[encoding]):
            return self.classifier.predict(None, threshold=0.7, max_distance=0.6)

    def test_known_face_is_matched(self):
        self.assertEqual(self.predict(self.alice_center)[0], "alice")
        self.assertEqual(self.predict(self.bob_center)[0], "bob")

    def test_stranger_is_rejected_even_when_svc_is_confident(self):
        stranger = self.bob_center + 0.2  # far beyond both students, but on bob's side
        self.assertIsNone(self.predict(stranger)[0])

    def test_no_face_found(self):
        with mock.patch.object(face_engine.face_recognition, "face_locations", return_value=[]), \
                mock.patch.object(face_engine.face_recognition, "face_encodings", return_value=[]):
            self.assertEqual(self.classifier.predict(None, 0.7, 0.6), (None, 0.0))

    def test_missing_model_raises(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(FACE_DATA_DIR=Path(tmp)):
            with self.assertRaises(face_engine.ModelNotTrainedError):
                face_engine.Classifier.load()


class FormTests(TestCase):
    def test_date_range_must_be_ordered(self):
        form = DateRangeForm({"date_from": "2026-09-10", "date_to": "2026-09-01"})
        self.assertFalse(form.is_valid())

    def test_username_must_exist(self):
        User.objects.create_user("alice")
        data = {"date_from": "2026-09-01", "date_to": "2026-09-10"}
        self.assertTrue(UsernameAndDateRangeForm({**data, "username": "alice"}).is_valid())
        self.assertFalse(UsernameAndDateRangeForm({**data, "username": "ghost"}).is_valid())


class ViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="pw", is_staff=True)
        self.student = User.objects.create_user("alice", password="pw")

    def test_public_pages(self):
        for name in ["home", "login"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_admin_pages_require_staff(self):
        admin_pages = ["add-photos", "train", "register", "view-attendance-home",
                       "view-attendance-date", "view-attendance-employee"]
        self.client.force_login(self.student)
        for name in admin_pages:
            self.assertRedirects(self.client.get(reverse(name)), reverse("not-authorised"))
        self.client.force_login(self.admin)
        for name in admin_pages:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_student_page_rejects_admin(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(reverse("view-my-attendance-employee-login")), reverse("not-authorised"))

    def test_dashboard_per_role(self):
        self.client.force_login(self.admin)
        self.assertTemplateUsed(self.client.get(reverse("dashboard")), "recognition/admin_dashboard.html")
        self.client.force_login(self.student)
        self.assertTemplateUsed(self.client.get(reverse("dashboard")), "recognition/employee_dashboard.html")

    def test_mark_attendance_requires_post(self):
        self.assertEqual(self.client.get(reverse("mark-your-attendance")).status_code, 405)

    @mock.patch.object(face_engine, "recognise_faces", return_value={"alice"})
    def test_mark_in_and_out(self, _):
        response = self.client.post(reverse("mark-your-attendance"), follow=True)
        self.assertContains(response, "Checked in: alice.")
        self.client.post(reverse("mark-your-attendance-out"))
        self.assertEqual(list(Time.objects.values_list("out", flat=True).order_by("id")), [False, True])

    @mock.patch.object(face_engine, "recognise_faces", side_effect=face_engine.ModelNotTrainedError("not trained"))
    def test_mark_in_reports_engine_errors(self, _):
        response = self.client.post(reverse("mark-your-attendance"), follow=True)
        self.assertContains(response, "not trained")
        self.assertFalse(Time.objects.exists())

    def test_reports_render_rows_and_chart(self):
        today = datetime.date.today()
        attendance.mark_in({"alice"}, when=datetime.datetime.combine(today, datetime.time(9)))
        attendance.mark_out({"alice"}, when=datetime.datetime.combine(today, datetime.time(17)))

        self.client.force_login(self.admin)
        response = self.client.get(reverse("view-attendance-home"))
        self.assertEqual((response.context["total_num_of_emp"], response.context["emp_present_today"]), (1, 1))
        self.assertTrue(response.context["this_week_chart"].startswith("data:image/png;base64,"))

        response = self.client.post(reverse("view-attendance-date"), {"date": today.isoformat()})
        self.assertContains(response, "8 hrs 0 mins")
        self.assertIsNotNone(response.context["chart"])

        span = {"date_from": today.isoformat(), "date_to": today.isoformat()}
        response = self.client.post(reverse("view-attendance-employee"), {"username": "alice", **span})
        self.assertContains(response, "8 hrs 0 mins")

        self.client.force_login(self.student)
        response = self.client.post(reverse("view-my-attendance-employee-login"), span)
        self.assertContains(response, "8 hrs 0 mins")

    def test_report_with_no_records_warns(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("view-attendance-date"), {"date": "2001-01-01"})
        self.assertContains(response, "No records for the selected date.")

    def test_register_creates_student(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register"),
            {"username": "bob", "password1": "a-long-Passw0rd!", "password2": "a-long-Passw0rd!"},
        )
        self.assertRedirects(response, reverse("add-photos"))
        self.assertTrue(User.objects.filter(username="bob", is_staff=False).exists())

    def test_logout_via_post(self):
        self.client.force_login(self.student)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))
