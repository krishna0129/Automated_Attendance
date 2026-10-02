"""
Face detection, sample capture, recognition and classifier training.

The camera is opened on the machine running the Django server (a kiosk
setup), and an OpenCV window shows the live feed. Press ``q`` to close it.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import dlib
import face_recognition
import face_recognition_models
import imutils
import joblib
import numpy as np
from django.conf import settings
from django.contrib.auth.models import User
from imutils.face_utils import FaceAligner, rect_to_bb
from sklearn.manifold import TSNE
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import SVC

from . import charts
from .face_storage import FaceImageStore

logger = logging.getLogger(__name__)

FRAME_WIDTH = 800
ALIGNED_FACE_WIDTH = 96
GREEN = (0, 255, 0)
QUIT_KEY = ord("q")


class FaceEngineError(Exception):
    """Base class for errors shown to the user."""


class CameraError(FaceEngineError):
    pass


class ModelNotTrainedError(FaceEngineError):
    pass


class NotEnoughDataError(FaceEngineError):
    pass


def _config(key: str):
    return settings.FACE_RECOGNITION[key]


def classifier_path() -> Path:
    return Path(settings.FACE_DATA_DIR) / "classifier.joblib"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _detector():
    return dlib.get_frontal_face_detector()


@lru_cache(maxsize=1)
def _aligner() -> FaceAligner:
    local = Path(settings.FACE_DATA_DIR) / "shape_predictor_68_face_landmarks.dat"
    # Fall back to the copy bundled with the face_recognition_models package.
    path = local if local.exists() else Path(face_recognition_models.pose_predictor_model_location())
    return FaceAligner(dlib.shape_predictor(str(path)), desiredFaceWidth=ALIGNED_FACE_WIDTH)


@dataclass
class Classifier:
    svc: SVC
    encoder: LabelEncoder

    @classmethod
    def load(cls) -> Classifier:
        path = classifier_path()
        if not path.exists():
            raise ModelNotTrainedError("The recognition model has not been trained yet. Ask an administrator to train it.")
        data = joblib.load(path)
        return cls(svc=data["svc"], encoder=data["encoder"])

    def save(self) -> None:
        path = classifier_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"svc": self.svc, "encoder": self.encoder}, path)

    def predict(self, face: np.ndarray, threshold: float) -> tuple[str | None, float]:
        """Return (username, probability), or (None, probability) if no confident match."""
        encodings = face_recognition.face_encodings(face, known_face_locations=face_recognition.face_locations(face))
        if not encodings:
            return None, 0.0
        probabilities = self.svc.predict_proba(encodings[:1])[0]
        best = int(np.argmax(probabilities))
        if probabilities[best] <= threshold:
            return None, float(probabilities[best])
        return str(self.encoder.inverse_transform([best])[0]), float(probabilities[best])


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------


@dataclass
class DetectedFace:
    box: tuple[int, int, int, int]  # x, y, w, h
    aligned: np.ndarray


@contextmanager
def camera_window(title: str) -> Iterator[Iterator[tuple[np.ndarray, list[DetectedFace]]]]:
    """
    Open the webcam and yield an iterator of (frame, faces) pairs.

    The iterator stops when the user presses ``q``. The camera and window are
    always released on exit.
    """
    capture = cv2.VideoCapture(_config("CAMERA_INDEX"))
    if not capture.isOpened():
        capture.release()
        raise CameraError("Could not open the camera. Check that a webcam is connected.")

    def frames():
        while True:
            ok, frame = capture.read()
            if not ok:
                raise CameraError("Lost the camera feed.")
            frame = imutils.resize(frame, width=FRAME_WIDTH)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = [
                DetectedFace(box=rect_to_bb(rect), aligned=_aligner().align(frame, gray, rect))
                for rect in _detector()(gray, 0)
            ]
            yield frame, faces
            cv2.imshow(title, frame)
            if cv2.waitKey(1) & 0xFF == QUIT_KEY:
                return

    try:
        yield frames()
    finally:
        capture.release()
        cv2.destroyAllWindows()
        # Let the window manager process the close event.
        cv2.waitKey(1)


def _label(frame: np.ndarray, face: DetectedFace, text: str) -> None:
    x, y, w, h = face.box
    cv2.rectangle(frame, (x, y), (x + w, y + h), GREEN, 1)
    cv2.putText(frame, text, (x + 6, y + h - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, GREEN, 1)


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------


def capture_samples(user: User, store: FaceImageStore) -> int:
    """
    Capture face samples of ``user`` from the webcam, replacing any existing ones.

    Returns the number of samples stored.
    """
    target = _config("SAMPLES_PER_USER")
    store.clear(user)
    saved = 0
    with camera_window(f"Add photos - {user.username} - press q to stop") as frames:
        for frame, faces in frames:
            for face in faces:
                ok, jpeg = cv2.imencode(".jpg", face.aligned)
                if ok:
                    store.save(user, jpeg.tobytes())
                    saved += 1
                _label(frame, face, f"{saved}/{target}")
            if saved >= target:
                break
    logger.info("Captured %d samples for %s", saved, user.username)
    return saved


def recognise_faces(window_title: str) -> set[str]:
    """
    Run the webcam until ``q`` is pressed and return the usernames recognised.

    A person counts as recognised once they were matched in at least
    FACE_RECOGNITION["MIN_HITS"] frames, which filters out one-off false matches.
    """
    classifier = Classifier.load()
    threshold = _config("MATCH_THRESHOLD")
    min_hits = _config("MIN_HITS")
    hits: Counter[str] = Counter()

    with camera_window(f"{window_title} - press q when done") as frames:
        for frame, faces in frames:
            for face in faces:
                username, probability = classifier.predict(face.aligned, threshold)
                if username is None:
                    _label(frame, face, "unknown")
                    continue
                hits[username] += 1
                status = "OK" if hits[username] >= min_hits else "..."
                _label(frame, face, f"{username} {probability:.2f} {status}")

    return {username for username, n in hits.items() if n >= min_hits}


@dataclass
class TrainingResult:
    images_used: int
    images_removed: int
    people: list[str]
    seconds: float
    visualisation: str  # data: URI of a 2-D embedding plot


def train_classifier(store: FaceImageStore) -> TrainingResult:
    """
    Encode every stored face image and fit a new classifier.

    Images in which no face can be found are deleted from the store.
    """
    started = time.monotonic()
    encodings: list[np.ndarray] = []
    labels: list[str] = []
    removed = 0

    for stored in store.iter_images():
        image = cv2.imdecode(np.frombuffer(stored.data, np.uint8), cv2.IMREAD_COLOR)
        found = face_recognition.face_encodings(image) if image is not None else []
        if not found:
            store.delete(stored.ref)
            removed += 1
            continue
        encodings.append(found[0])
        labels.append(stored.username)

    people = sorted(set(labels))
    if len(people) < 2:
        raise NotEnoughDataError("Training needs photos of at least two students. Add photos and try again.")

    X = np.array(encodings)
    encoder = LabelEncoder().fit(labels)
    svc = SVC(kernel="linear", probability=True).fit(X, encoder.transform(labels))
    Classifier(svc=svc, encoder=encoder).save()

    perplexity = min(30.0, len(X) - 1.0)
    embedded = TSNE(n_components=2, perplexity=perplexity, init="pca", random_state=0).fit_transform(X)

    result = TrainingResult(
        images_used=len(X),
        images_removed=removed,
        people=people,
        seconds=time.monotonic() - started,
        visualisation=charts.scatter_by_label(embedded, labels),
    )
    logger.info("Trained classifier on %d images of %d people", result.images_used, len(people))
    return result
