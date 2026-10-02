from collections import Counter

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from recognition.face_storage import get_face_store

BACKENDS = ["filesystem", "database"]


class Command(BaseCommand):
    help = (
        "Copy captured face images from one storage backend to another, e.g. from the "
        "local training_dataset folder into the database (PostgreSQL)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="source", choices=BACKENDS, default="filesystem")
        parser.add_argument("--to", dest="target", choices=BACKENDS, default="database")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete a student's existing images in the target before copying.",
        )

    def handle(self, *args, source, target, replace, **options):
        if source == target:
            raise CommandError("--from and --to must be different backends.")
        source_store, target_store = get_face_store(source), get_face_store(target)

        users = {u.username: u for u in User.objects.all()}
        copied: Counter[str] = Counter()
        skipped: set[str] = set()
        cleared: set[str] = set()

        for image in source_store.iter_images():
            user = users.get(image.username)
            if user is None:
                skipped.add(image.username)
                continue
            if replace and user.username not in cleared:
                target_store.clear(user)
                cleared.add(user.username)
            target_store.save(user, image.data)
            copied[user.username] += 1

        for username, n in sorted(copied.items()):
            self.stdout.write(f"  {username}: {n} images")
        if skipped:
            self.stderr.write(self.style.WARNING(f"Skipped unknown usernames: {', '.join(sorted(skipped))}"))
        self.stdout.write(self.style.SUCCESS(f"Copied {sum(copied.values())} images from {source} to {target}."))
