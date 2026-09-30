"""
Management command: tag_subtopics

Two-stage LLM pipeline:
  1. For each chapter, generate a small canonical list of subtopics.
  2. For each MCQ in that chapter, classify it against that chapter's list.

Run modes:
  --dry-run   Uses stub functions instead of real API calls. Free, safe,
              lets you verify the whole flow works before spending anything.
  (default)   Uses the real LLM calls. Costs money. Only run once --dry-run
              output looks correct.

Usage:
  python manage.py tag_subtopics --dry-run
  python manage.py tag_subtopics --dry-run --chapter-id 5   (test one chapter only)
  python manage.py tag_subtopics                            (the real, paid run)
"""

from django.core.management.base import BaseCommand
from ZehnifyApp.models import Chapter, MCQ


# ---------------------------------------------------------------------------
# STAGE 1: generate a chapter's subtopic list
# ---------------------------------------------------------------------------

def generate_subtopics_stub(chapter):
    """Fake version — returns placeholder subtopics so the pipeline can be
    tested for free. Replace generate_subtopics() below with a real call
    when ready to spend money."""
    return [f"{chapter.name} - Topic {i}" for i in range(1, 5)]


def generate_subtopics_real(chapter):
    """TODO tonight: call the LLM here.
    Prompt should include chapter.name and chapter.subject.name, and ask
    for 4-8 short, mutually exclusive subtopic labels as a JSON list.
    Must return a plain Python list of strings."""
    raise NotImplementedError("Wire up the real API call here tonight")


# ---------------------------------------------------------------------------
# STAGE 2: classify one MCQ against its chapter's subtopic list
# ---------------------------------------------------------------------------

def classify_mcq_stub(mcq, subtopic_list):
    """Fake version — just picks the first subtopic in the list every time.
    Replace classify_mcq() below with a real call when ready."""
    return subtopic_list[0] if subtopic_list else "Uncategorized"


def classify_mcq_real(mcq, subtopic_list):
    """TODO tonight: call the LLM here.
    Prompt should include mcq.question_text, options A-D, and the
    constrained subtopic_list. Must return exactly one label from that
    list, or 'Uncategorized' if it doesn't fit / the call fails."""
    raise NotImplementedError("Wire up the real API call here tonight")


class Command(BaseCommand):
    help = "Tag every MCQ with a subtopic, chapter by chapter."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Use free stub functions instead of real LLM calls.",
        )
        parser.add_argument(
            "--chapter-id",
            type=int,
            default=None,
            help="Only process this one chapter (for testing).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        chapter_id = options["chapter_id"]

        generate_subtopics = generate_subtopics_stub if dry_run else generate_subtopics_real
        classify_mcq = classify_mcq_stub if dry_run else classify_mcq_real

        chapters = Chapter.objects.all()
        if chapter_id:
            chapters = chapters.filter(id=chapter_id)

        mode_label = "DRY RUN (free, stubbed)" if dry_run else "LIVE RUN (real API calls, costs money)"
        self.stdout.write(self.style.WARNING(f"Mode: {mode_label}"))
        self.stdout.write(f"Chapters to process: {chapters.count()}")

        total_tagged = 0

        for chapter in chapters:
            mcqs = MCQ.objects.filter(chapter=chapter)
            if not mcqs.exists():
                continue

            self.stdout.write(f"\n--- {chapter.name} ({mcqs.count()} MCQs) ---")

            try:
                subtopics = generate_subtopics(chapter)
            except NotImplementedError as e:
                self.stdout.write(self.style.ERROR(f"  Skipped: {e}"))
                continue

            self.stdout.write(f"  Subtopics: {subtopics}")

            for mcq in mcqs:
                try:
                    label = classify_mcq(mcq, subtopics)
                except NotImplementedError as e:
                    self.stdout.write(self.style.ERROR(f"  Skipped: {e}"))
                    break
                except Exception as e:
                    label = "Uncategorized"
                    self.stdout.write(self.style.WARNING(f"  MCQ {mcq.id} failed, using fallback: {e}"))

                mcq.subtopic = label
                mcq.save(update_fields=["subtopic"])
                total_tagged += 1

        self.stdout.write(self.style.SUCCESS(f"\nDone. Tagged {total_tagged} MCQs."))