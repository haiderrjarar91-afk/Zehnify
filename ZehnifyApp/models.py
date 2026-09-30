from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from zoneinfo import ZoneInfo
import re

class UserProfile(models.Model):
    STREAM_CHOICES = [
        ('PRE_ENG', 'Pre-Engineering'),
        ('PRE_MED', 'Pre-Medical'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    stream = models.CharField(max_length=10, choices=STREAM_CHOICES)


class Subject(models.Model):
    name = models.CharField(max_length=20)
    stream = models.CharField(max_length=10, choices=[
        ('PRE_ENG', 'Pre-Engineering'),
        ('PRE_MED', 'Pre-Medical'),
        ('BOTH', 'both')], default='BOTH')
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

    class Meta:
        ordering = ['order']

    def save(self, *args, **kwargs):
        if self.url_path:
            # Extracts 11-char ID cleanly from embed, standard watch, youtu.be, or raw IDs
            pattern = r'(?:v=|\/embed\/|youtu\.be\/|\/watch\?v=|^|\/)([a-zA-Z0-9_-]{11})'
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
    time_taken_seconds = models.IntegerField(default=0) # Useful for timer tracking
    date_taken = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.chapter.name} ({self.percentage}%)"


class UserAnswer(models.Model):
    exam_attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='user_answers')
    mcq = models.ForeignKey(MCQ, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=10, blank=True, null=True) # E.g., 'A', 'B', 'C', 'D' or None
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
    is_bookmarked = models.BooleanField(default=False, help_text="Mark as an error or for future review")
    last_attempted = models.DateTimeField(auto_now=True)

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

    from datetime import timedelta
from zoneinfo import ZoneInfo

PKT = ZoneInfo("Asia/Karachi")

def get_user_streak(user):
    """
    Returns the user's current consecutive-day activity streak.
    A day counts if the user watched a lecture, attempted a practice
    question, or took an exam on that day (Pakistan local date).
    """
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

    # Streak only counts as "current" if the most recent activity was
    # today or yesterday — otherwise it's broken, not just paused
    if sorted_dates[0] not in (today, today - timedelta(days=1)):
        return 0

    streak = 1
    for i in range(len(sorted_dates) - 1):
        gap = (sorted_dates[i] - sorted_dates[i + 1]).days
        if gap == 1:
            streak += 1
        elif gap == 0:
            continue  # shouldn't happen since it's a set, but harmless
        else:
            break

    return streak