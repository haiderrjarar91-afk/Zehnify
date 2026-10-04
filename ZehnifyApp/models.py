from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from zoneinfo import ZoneInfo
import re
import random
from collections import defaultdict


class UserProfile(models.Model):
    STREAM_CHOICES = [
        ('PRE_ENG', 'Pre-Engineering'),
        ('PRE_MED', 'Pre-Medical'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    stream = models.CharField(max_length=10, choices=STREAM_CHOICES)


class Subject(models.Model):
    name = models.CharField(max_length=20)
    stream = models.CharField(
        max_length=10,
        choices=[
            ('PRE_ENG', 'Pre-Engineering'),
            ('PRE_MED', 'Pre-Medical'),
            ('BOTH', 'both')
        ],
        default='BOTH'
    )

    def __str__(self):
        return self.name


class Chapter(models.Model):
    GRADE_CHOICES = [
        (11, '11th Grade'),
        (12, '12th Grade'),
    ]
    name = models.CharField(max_length=100)
    weightage = models.IntegerField(default=1)
    stream = models.CharField(max_length=20)
    grade = models.IntegerField(choices=GRADE_CHOICES, default=11)
    subject = models.ForeignKey(Subject, related_name='chapters', on_delete=models.CASCADE)
    is_published = models.BooleanField(default=False)
    key_formulas = models.TextField(
        blank=True,
        null=True,
        help_text=r"Enter LaTeX formulas, one per line (e.g., \sqrt{4} or \frac{a}{b})"
    )

    def __str__(self):
        return f"{self.name} ({self.grade}th)"


class ChapterVideo(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='videos')
    title = models.CharField(max_length=200, default='Untitled Lecture')
    url_path = models.CharField(max_length=200, help_text="Paste YouTube Video ID or full link")
    order = models.PositiveIntegerField(default=1)
    subtopic = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        ordering = ['order']

    def save(self, *args, **kwargs):
        if self.url_path:
            pattern = r'(?:v=|\/embed\/|youtu\.be\/|\/watch\?v=|^|\/)([a-zA-Z0-9\_-]{11})'
            match = re.search(pattern, self.url_path)
            if match:
                self.url_path = match.group(1)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.chapter.name} - {self.title}"


class MCQ(models.Model):
    class Meta:
        verbose_name_plural = "MCQs"

    chapter = models.ForeignKey(Chapter, related_name='mcqs', on_delete=models.CASCADE)
    question_text = models.TextField()
    A = models.TextField()
    B = models.TextField()
    C = models.TextField()
    D = models.TextField()
    correct_option = models.CharField(max_length=20)
    master_explanation = models.TextField(blank=True, null=True)
    is_exam_question = models.BooleanField(default=False)
    diagram = models.ImageField(upload_to='mcq_diagrams/', blank=True, null=True)
    subtopic = models.CharField(max_length=100, blank=True, default='')

    def __str__(self):
        return self.question_text


class ExamAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_attempts')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    percentage = models.IntegerField(default=0)
    time_taken_seconds = models.IntegerField(default=0)
    date_taken = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.chapter.name} ({self.percentage}%)"


class UserAnswer(models.Model):
    exam_attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='user_answers')
    mcq = models.ForeignKey(MCQ, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=10, blank=True, null=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.exam_attempt.user.username} - Q{self.mcq.id}: {self.selected_option}"


class Userchaptermastery(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    percentage = models.IntegerField(default=0)
    date_taken = models.DateTimeField(default=timezone.now)


class MCQAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mcq_attempts')
    mcq = models.ForeignKey(MCQ, on_delete=models.CASCADE, related_name='attempts')
    selected_option = models.CharField(max_length=10, blank=True, null=True)
    is_correct = models.BooleanField(default=False)
    is_bookmarked = models.BooleanField(
        default=False,
        help_text="True = this question is in the student's My Mistakes log"
    )
    last_attempted = models.DateTimeField(auto_now=True)

    # Optional, filled in later by the student on the My Mistakes page.
    # The allowed mistake types live in views.MISTAKE_TYPES (not as field
    # choices) so the list can change without a migration.
    mistake_type = models.CharField(max_length=30, blank=True, default='')
    reflection = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        unique_together = ('user', 'mcq')

    def __str__(self):
        return f"{self.user.username} - Q{self.mcq.id}: {self.selected_option} (Correct: {self.is_correct})"


class VideoProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_progress')
    video = models.ForeignKey(ChapterVideo, on_delete=models.CASCADE, related_name='progress')
    watched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'video')

    def __str__(self):
        return f"{self.user.username} - {self.video.title}"


class ChapterNote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chapter_notes')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='student_notes')
    formulas = models.TextField(blank=True, help_text="Supports LaTeX syntax for math symbols")
    reminders = models.TextField(blank=True)
    goals = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'chapter')

    def __str__(self):
        return f"{self.user.username} - Notes for {self.chapter.name}"


# ---------------------------------------------------------------------------
# MIXED PRACTICE
# ---------------------------------------------------------------------------

class MixedPracticeAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mixed_practice_attempts')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    percentage = models.IntegerField(default=0)
    date_taken = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - Mixed Practice: {self.chapter.name} ({self.percentage}%)"


class MixedPracticeAnswer(models.Model):
    attempt = models.ForeignKey(MixedPracticeAttempt, on_delete=models.CASCADE, related_name='answers')
    mcq = models.ForeignKey(MCQ, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=1)
    selected_option = models.CharField(max_length=10, blank=True, null=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.attempt.user.username} - Q{self.mcq.id}: {self.selected_option}"


class SubtopicPracticeAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subtopic_practice_attempts')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='subtopic_practice_attempts')
    subtopic = models.CharField(max_length=100)
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    percentage = models.IntegerField(default=0)
    date_taken = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.chapter.name} - {self.subtopic} ({self.percentage}%)"


PKT = ZoneInfo("Asia/Karachi")


def get_user_streak(user):
    mcq_dates = MCQAttempt.objects.filter(user=user).values_list('last_attempted', flat=True)
    exam_dates = ExamAttempt.objects.filter(user=user).values_list('date_taken', flat=True)
    video_dates = VideoProgress.objects.filter(user=user).values_list('watched_at', flat=True)

    all_local_dates = set()
    for dt in list(mcq_dates) + list(exam_dates) + list(video_dates):
        if dt is not None:
            all_local_dates.add(dt.astimezone(PKT).date())

    if not all_local_dates:
        return 0

    today = timezone.now().astimezone(PKT).date()
    sorted_dates = sorted(all_local_dates, reverse=True)

    if sorted_dates[0] not in (today, today - timedelta(days=1)):
        return 0

    streak = 1
    for i in range(len(sorted_dates) - 1):
        gap = (sorted_dates[i] - sorted_dates[i + 1]).days
        if gap == 1:
            streak += 1
        elif gap == 0:
            continue
        else:
            break

    return streak


def get_chapter_subtopics(chapter):
    return list(
        MCQ.objects.filter(chapter=chapter, is_exam_question=False)
        .exclude(subtopic='')
        .values_list('subtopic', flat=True)
        .distinct()
        .order_by('subtopic')
    )


def get_subtopic_sample(chapter, subtopic, count):
    pool = list(MCQ.objects.filter(chapter=chapter, subtopic=subtopic, is_exam_question=False))
    if len(pool) <= count:
        return pool
    return random.sample(pool, count)


def get_user_subtopic_mastery(user, chapter):
    """
    Recency-based mastery: whichever is more recent — the latest completed
    SubtopicPracticeAttempt for a subtopic, or that subtopic's slice of the
    user's latest ExamAttempt — determines current mastery. Mixed Practice
    never contributes here; it's a separate, intentionally unscored signal.
    """
    subtopics = get_chapter_subtopics(chapter)

    mastery = {
        subtopic: {
            'mastery': None,
            'source': None,
            'practice_percentage': None,
            'practice_score': 0,
            'practice_total': 0,
            'exam_percentage': None,
            'exam_score': 0,
            'exam_total': 0,
        }
        for subtopic in subtopics
    }

    latest_exam = (
        ExamAttempt.objects.filter(user=user, chapter=chapter).order_by('-date_taken').first()
    )

    exam_percentages = {}
    exam_date = None

    if latest_exam:
        exam_date = latest_exam.date_taken
        exam_stats = defaultdict(lambda: {'correct': 0, 'total': 0})
        answers = latest_exam.user_answers.select_related('mcq').all()

        for answer in answers:
            subtopic = answer.mcq.subtopic
            if subtopic not in mastery:
                continue
            exam_stats[subtopic]['total'] += 1
            if answer.is_correct:
                exam_stats[subtopic]['correct'] += 1

        for subtopic, stats in exam_stats.items():
            total = stats['total']
            correct = stats['correct']
            if total > 0:
                percentage = round((correct / total) * 100)
                mastery[subtopic]['exam_score'] = correct
                mastery[subtopic]['exam_total'] = total
                mastery[subtopic]['exam_percentage'] = percentage
                exam_percentages[subtopic] = percentage

    practice_attempts = (
        SubtopicPracticeAttempt.objects.filter(user=user, chapter=chapter, subtopic__in=subtopics)
        .order_by('subtopic', '-date_taken')
    )

    latest_practice = {}
    for attempt in practice_attempts:
        if attempt.subtopic not in latest_practice:
            latest_practice[attempt.subtopic] = attempt

    for subtopic in subtopics:
        practice = latest_practice.get(subtopic)

        if practice:
            mastery[subtopic]['practice_percentage'] = practice.percentage
            mastery[subtopic]['practice_score'] = practice.score
            mastery[subtopic]['practice_total'] = practice.total_questions

        has_exam = subtopic in exam_percentages
        has_practice = practice is not None

        if has_exam and has_practice:
            # Whichever happened more recently wins.
            if exam_date >= practice.date_taken:
                mastery[subtopic]['mastery'] = exam_percentages[subtopic]
                mastery[subtopic]['source'] = 'exam'
            else:
                mastery[subtopic]['mastery'] = practice.percentage
                mastery[subtopic]['source'] = 'practice'
        elif has_practice:
            mastery[subtopic]['mastery'] = practice.percentage
            mastery[subtopic]['source'] = 'practice'
        elif has_exam:
            mastery[subtopic]['mastery'] = exam_percentages[subtopic]
            mastery[subtopic]['source'] = 'exam'

    return mastery