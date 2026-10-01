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
  python manage.py tag_subtopics --chapter-id 1             (real run, one chapter, costs a few cents)
  python manage.py tag_subtopics                            (the real, full paid run)
"""

import json
from django.core.management.base import BaseCommand
from ZehnifyApp.models import Chapter, MCQ
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment automatically


# ---------------------------------------------------------------------------
# STAGE 1: generate a chapter's subtopic list (Sonnet — runs 34 times total)
# ---------------------------------------------------------------------------

def generate_subtopics_stub(chapter):
    return [f"{chapter.name} - Topic {i}" for i in range(1, 5)]


def generate_subtopics_real(chapter):
    prompt = f"""This is a chapter called "{chapter.name}" from a {chapter.subject.name} course, \
for Pakistani intermediate-level (11th/12th grade) students preparing for competitive entry exams \
(ECAT/MDCAT).

Break this chapter down into 4 to 8 distinct, commonly-tested sub-topics.

Respond with ONLY a JSON array of short string labels. No explanation, no markdown fences, \
no extra text. Example format: ["Label One", "Label Two", "Label Three"]"""

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = next((block.text for block in response.content if block.type == "text"), "").strip()

    try:
        subtopics = json.loads(raw_text)
        if isinstance(subtopics, list) and all(isinstance(s, str) for s in subtopics) and subtopics:
            return subtopics
    except (json.JSONDecodeError, IndexError):
        pass

    # Fallback: parsing failed or shape was wrong — don't crash the whole run
    return ["General"]


# ---------------------------------------------------------------------------
# STAGE 2: classify one MCQ against its chapter's subtopic list (Haiku — runs
# once per MCQ, ~4,866 times total)
# ---------------------------------------------------------------------------

def classify_mcq_stub(mcq, subtopic_list):
    return subtopic_list[0] if subtopic_list else "Uncategorized"


def classify_mcq_real(mcq, subtopic_list):
    options_block = f"A) {mcq.A}\nB) {mcq.B}\nC) {mcq.C}\nD) {mcq.D}"
    labels_block = "\n".join(f"- {s}" for s in subtopic_list)

    prompt = f"""Question: {mcq.question_text}

{options_block}

Allowed sub-topics (choose exactly one, copying it EXACTLY as written below):
{labels_block}

Respond with ONLY the exact matching sub-topic label. No explanation, no punctuation, no quotes."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        label = next((block.text for block in response.content if block.type == "text"), "").strip()
    except Exception:
        return "Uncategorized"

    # Strict match required — anything else (paraphrase, extra text, hallucinated
    # label) falls back rather than fragmenting the aggregation later
    if label in subtopic_list:
        return label
    return "Uncategorized"


class Command(BaseCommand):
    help = "Tag every MCQ with a subtopic, chapter by chapter."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--chapter-id", type=int, default=None)

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
        uncategorized_count = 0

        for chapter in chapters:
            mcqs = MCQ.objects.filter(chapter=chapter)
            if not mcqs.exists():
                continue

            self.stdout.write(f"\n--- {chapter.name} ({mcqs.count()} MCQs) ---")
            subtopics = generate_subtopics(chapter)
            self.stdout.write(f"  Subtopics: {subtopics}")

            for mcq in mcqs:
                label = classify_mcq(mcq, subtopics)
                if label == "Uncategorized":
                    uncategorized_count += 1
                mcq.subtopic = label
                mcq.save(update_fields=["subtopic"])
                total_tagged += 1

        self.stdout.write(self.style.SUCCESS(f"\nDone. Tagged {total_tagged} MCQs."))
        self.stdout.write(f"Uncategorized (fallback) count: {uncategorized_count}")