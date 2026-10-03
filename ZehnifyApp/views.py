from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from collections import defaultdict
from urllib.parse import quote
import random

from .models import (
    Chapter, MCQ, ChapterVideo, Subject, 
    Userchaptermastery, VideoProgress, UserAnswer, 
    ExamAttempt, UserProfile, MCQAttempt, ChapterNote,
    get_user_streak, MixedPracticeAttempt, MixedPracticeAnswer,
    get_chapter_subtopics, get_subtopic_sample
)
from .forms import StudentRegisterationForm


def signup(request):
    if request.method == 'POST':
        form = StudentRegisterationForm(request.POST)
        if form.is_valid():
            user = form.save()
            selected_stream = form.cleaned_data.get('stream')
            UserProfile.objects.create(user=user, stream=selected_stream)
            return redirect('login_page')
    else:
        form = StudentRegisterationForm()
    return render(request, 'zehnify/signup.html', {'form': form})    


@login_required
def home(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    try:
        user_stream = request.user.userprofile.stream
    except UserProfile.DoesNotExist:
        user_stream = 'BOTH'
    subjects = Subject.objects.filter(stream__in=[user_stream, 'BOTH'])
    subject_data = []
    for subject in subjects:
        subject_chapters = subject.chapters.all()
        total_possible_weight = 0
        total_calculated_weight = 0
        for chapter in subject_chapters:
            total_possible_weight += chapter.weightage
            mastery_record = Userchaptermastery.objects.filter(user=request.user, chapter=chapter).first()
            percentage = mastery_record.percentage if mastery_record else 0
            total_calculated_weight += (percentage * chapter.weightage)
        subject_mastery = round(total_calculated_weight / total_possible_weight) if total_possible_weight > 0 else 0
        subject_data.append({'subject': subject, 'subject_mastery': subject_mastery})    
    streak = get_user_streak(request.user)
    context = {'subject_data': subject_data, 'subjects': subjects, 'streak': streak}    
    return render(request, 'zehnify/home.html', context)


@login_required
def sub_details(request, subject_id):
    try:
        user_stream = request.user.userprofile.stream
    except UserProfile.DoesNotExist:
        user_stream = 'BOTH'
    subject = get_object_or_404(Subject, id=subject_id, stream__in=[user_stream, 'BOTH'])
    chapters_11th = Chapter.objects.filter(subject=subject, grade=11)
    chapters_12th = Chapter.objects.filter(subject=subject, grade=12)
    return render(request, 'zehnify/subject_detail.html', {
        'subject': subject, 'chapters_11th': chapters_11th, 'chapters_12th': chapters_12th,
    })


@login_required
def chapterdetail(request, chapter_id):
    chapter = get_object_or_404(Chapter, id=chapter_id)
    mastery_record = Userchaptermastery.objects.filter(user=request.user, chapter=chapter).first()
    mastery = mastery_record.percentage if mastery_record else 0
    latest_attempt = ExamAttempt.objects.filter(user=request.user, chapter=chapter).order_by('-date_taken').first()
    return render(request, 'zehnify/chapter_detail.html', {
        'chapter': chapter, 'mastery': mastery, 'mastery_width': f"{mastery}%", 'latest_attempt': latest_attempt,
    })


@login_required
def practice(request, chapter_id):
    chapter = get_object_or_404(Chapter, id=chapter_id)
    practice_mcqs = MCQ.objects.filter(chapter=chapter, is_exam_question=False)
    filter_type = request.GET.get('filter', 'all')
    selected_subtopic = request.GET.get('subtopic', '')
    available_subtopics = (
        practice_mcqs.exclude(subtopic='').values_list('subtopic', flat=True).distinct().order_by('subtopic')
    )
    user_attempts = {a.mcq_id: a for a in MCQAttempt.objects.filter(user=request.user, mcq__chapter=chapter)}

    if request.method == 'POST':
        mcq_id = request.POST.get('mcq_id')
        selected_option = request.POST.get('selected_option')
        action = request.POST.get('action')
        if mcq_id:
            mcq = get_object_or_404(MCQ, id=mcq_id, chapter=chapter)
            attempt = MCQAttempt.objects.filter(user=request.user, mcq=mcq).first()
            if action == 'reset':
                if attempt:
                    attempt.delete()
            else:
                if selected_option:
                    attempt, created = MCQAttempt.objects.get_or_create(user=request.user, mcq=mcq)
                    attempt.selected_option = selected_option
                    attempt.is_correct = (selected_option == mcq.correct_option)
                    attempt.save()
        redirect_url = f"{request.path}?filter={filter_type}"
        if filter_type == 'subtopic' and selected_subtopic:
            redirect_url += f"&subtopic={quote(selected_subtopic)}"
        return redirect(redirect_url)

    mcq_data = []
    for index, m in enumerate(practice_mcqs, start=1):
        attempt = user_attempts.get(m.id)
        if filter_type == 'flagged':
            if not attempt or attempt.is_correct:
                continue
        elif filter_type == 'subtopic':
            if not selected_subtopic or m.subtopic != selected_subtopic:
                continue
        mcq_data.append({'mcq': m, 'attempt': attempt, 'counter': index})

    context = {
        'mcq_data': mcq_data, 'chapter': chapter, 'current_filter': filter_type,
        'available_subtopics': available_subtopics, 'selected_subtopic': selected_subtopic,
    }
    return render(request, 'zehnify/practice.html', context)


@login_required
def videos(request, chapter_id):
    chapter = get_object_or_404(Chapter, id=chapter_id)
    lectures = ChapterVideo.objects.filter(chapter=chapter)
    watched_ids = set(VideoProgress.objects.filter(user=request.user, video__chapter=chapter).values_list('video_id', flat=True))
    return render(request, 'zehnify/video.html', {'chapter': chapter, 'lectures': lectures, 'watched_ids': watched_ids})


@login_required
def notes(request, chapter_id):
    chapter = get_object_or_404(Chapter, id=chapter_id)
    note, created = ChapterNote.objects.get_or_create(user=request.user, chapter=chapter)
    if request.method == 'POST':
        note.formulas = request.POST.get('formulas', '')
        note.reminders = request.POST.get('reminders', '')
        note.goals = request.POST.get('goals', '')
        note.save()
        return redirect('notes_page', chapter_id=chapter.id)
    return render(request, 'zehnify/notes.html', {'chapter': chapter, 'note': note})


@login_required
def watch_lecture(request, video_id):
    lecture = get_object_or_404(ChapterVideo, pk=video_id)
    return render(request, 'zehnify/watch_lecture.html', {'lecture': lecture})


@login_required
def Exam(request, chapter_id):
    chapter = get_object_or_404(Chapter, id=chapter_id)
    mcqs = MCQ.objects.filter(chapter=chapter, is_exam_question=True)
    if request.method == 'POST':
        score = 0
        total = mcqs.count()
        attempt = ExamAttempt.objects.create(user=request.user, chapter=chapter, total_questions=total)
        for m in mcqs:
            user_choice = request.POST.get(f'Q{m.id}')
            is_correct = (user_choice == m.correct_option)
            if is_correct:
                score += 1
            UserAnswer.objects.create(exam_attempt=attempt, mcq=m, selected_option=user_choice, is_correct=is_correct)
        percentage = round((score / total) * 100) if total > 0 else 0
        attempt.score = score
        attempt.percentage = percentage
        attempt.save()
        Userchaptermastery.objects.update_or_create(
            user=request.user, chapter=chapter, defaults={'score': score, 'percentage': percentage}
        )
        return redirect('exam_review', chapter_id=chapter.id, attempt_id=attempt.id)
    return render(request, 'zehnify/exam.html', {'chapter': chapter, 'mcqs': mcqs, 'submitted': False})


@login_required
def exam_review(request, chapter_id, attempt_id):
    chapter = get_object_or_404(Chapter, id=chapter_id)
    attempt = get_object_or_404(ExamAttempt, id=attempt_id, chapter=chapter, user=request.user)
    answers = attempt.user_answers.select_related('mcq').all()

    subtopic_stats = defaultdict(lambda: {'wrong': 0, 'total': 0})
    for ans in answers:
        subtopic = ans.mcq.subtopic or 'Uncategorized'
        subtopic_stats[subtopic]['total'] += 1
        if not ans.is_correct:
            subtopic_stats[subtopic]['wrong'] += 1

    weakness_list = [
        {
            'subtopic': subtopic,
            'wrong': stats['wrong'],
            'total': stats['total'],
            'incorrect_percentage': round((stats['wrong'] / stats['total']) * 100) if stats['total'] else 0,
        }
        for subtopic, stats in subtopic_stats.items() if stats['wrong'] > 0
    ]
    weakness_list.sort(key=lambda item: (item['incorrect_percentage'], item['wrong']), reverse=True)

    return render(request, 'zehnify/exam_review.html', {
        'attempt': attempt, 'answers': answers, 'weakness_list': weakness_list,
    })


@login_required
@require_POST
def toggle_video_watched(request, video_id):
    video = get_object_or_404(ChapterVideo, pk=video_id)
    progress, created = VideoProgress.objects.get_or_create(user=request.user, video=video)
    if not created:
        progress.delete()
    return redirect('video_page', chapter_id=video.chapter.id)


# ---------------------------------------------------------------------------
# MIXED PRACTICE
# ---------------------------------------------------------------------------

@login_required
def mixed_practice_setup(request, chapter_id):
    chapter = get_object_or_404(Chapter, id=chapter_id)
    subtopics = get_chapter_subtopics(chapter)

    if request.method == 'POST':
        if not subtopics:
            return render(request, 'zehnify/mixed_practice_setup.html', {
                'chapter': chapter, 'subtopics': subtopics,
                'error': "This chapter doesn't have any tagged sub-topics yet, so Mixed Practice isn't available.",
            })
        try:
            total_requested = int(request.POST.get('total_questions', 20))
        except (TypeError, ValueError):
            total_requested = 20
        total_requested = max(1, min(total_requested, 100))

        n = len(subtopics)
        base = total_requested // n
        remainder = total_requested % n

        selected_mcqs = []
        shortages = []
        for i, s in enumerate(subtopics):
            count = base + (1 if i < remainder else 0)
            if count == 0:
                continue
            sample = get_subtopic_sample(chapter, s, count)
            selected_mcqs.extend(sample)
            if len(sample) < count:
                shortages.append(f"{s} ({len(sample)}/{count})")

        random.shuffle(selected_mcqs)

        if not selected_mcqs:
            return render(request, 'zehnify/mixed_practice_setup.html', {
                'chapter': chapter, 'subtopics': subtopics,
                'error': "No practice questions are available to build a session right now.",
            })

        attempt = MixedPracticeAttempt.objects.create(
            user=request.user, chapter=chapter, total_questions=len(selected_mcqs),
        )
        MixedPracticeAnswer.objects.bulk_create([
            MixedPracticeAnswer(attempt=attempt, mcq=mcq, order=i + 1)
            for i, mcq in enumerate(selected_mcqs)
        ])

        if shortages:
            request.session['mixed_practice_shortage_notice'] = (
                f"Requested {total_requested} questions, built {len(selected_mcqs)} "
                f"(short on: {', '.join(shortages)})."
            )

        return redirect('mixed_practice_session', attempt_id=attempt.id)

    return render(request, 'zehnify/mixed_practice_setup.html', {'chapter': chapter, 'subtopics': subtopics})


@login_required
def mixed_practice_session(request, attempt_id):
    attempt = get_object_or_404(MixedPracticeAttempt, id=attempt_id, user=request.user)
    answers = attempt.answers.select_related('mcq').order_by('order')

    if request.method == 'POST':
        score = 0
        for ans in answers:
            user_choice = request.POST.get(f'Q{ans.mcq.id}')
            is_correct = (user_choice == ans.mcq.correct_option)
            ans.selected_option = user_choice
            ans.is_correct = is_correct
            ans.save()
            if is_correct:
                score += 1
        total = answers.count()
        percentage = round((score / total) * 100) if total > 0 else 0
        attempt.score = score
        attempt.percentage = percentage
        attempt.save()
        return redirect('mixed_practice_review', attempt_id=attempt.id)

    shortage_notice = request.session.pop('mixed_practice_shortage_notice', None)
    return render(request, 'zehnify/mixed_practice_session.html', {
        'chapter': attempt.chapter, 'attempt': attempt, 'answers': answers, 'shortage_notice': shortage_notice,
    })


@login_required
def mixed_practice_review(request, attempt_id):
    attempt = get_object_or_404(MixedPracticeAttempt, id=attempt_id, user=request.user)
    answers = attempt.answers.select_related('mcq').order_by('order')

    subtopic_stats = defaultdict(lambda: {'wrong': 0, 'total': 0})
    for ans in answers:
        s = ans.mcq.subtopic or 'Uncategorized'
        subtopic_stats[s]['total'] += 1
        if not ans.is_correct:
            subtopic_stats[s]['wrong'] += 1

    weakness_list = [
        {'subtopic': k, 'wrong': v['wrong'], 'total': v['total']}
        for k, v in subtopic_stats.items() if v['wrong'] > 0
    ]
    weakness_list.sort(key=lambda x: x['wrong'], reverse=True)

    return render(request, 'zehnify/mixed_practice_review.html', {
        'attempt': attempt, 'answers': answers, 'weakness_list': weakness_list,
    })