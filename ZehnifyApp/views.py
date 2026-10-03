from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views.decorators.http import require_POST
from collections import defaultdict
from urllib.parse import quote, urlencode
import random

from .models import (
    Chapter,
    MCQ,
    ChapterVideo,
    Subject,
    Userchaptermastery,
    VideoProgress,
    UserAnswer,
    ExamAttempt,
    UserProfile,
    MCQAttempt,
    ChapterNote,
    get_user_streak,
    MixedPracticeAttempt,
    MixedPracticeAnswer,
    SubtopicPracticeAttempt,
    get_chapter_subtopics,
    get_subtopic_sample,
    get_user_subtopic_mastery,
)
from .forms import StudentRegisterationForm


# ---------------------------------------------------------------------------
# MY MISTAKES - settings
#
# The mistake-type list is a plain constant (not model field choices), so you
# can edit it any time without a migration. Already-saved values that are no
# longer in the list simply show up as "(old type)" in the dropdown.
# ---------------------------------------------------------------------------

MISTAKE_TYPES = [
    'Concept gap',
    'Forgot formula',
    'Calculation error',
    'Misread question',
    'Careless slip',
    'Guessed',
]

REFLECTION_MAX_WORDS = 20
REFLECTION_MAX_CHARS = 300


def signup(request):
    if request.method == 'POST':
        form = StudentRegisterationForm(request.POST)

        if form.is_valid():
            user = form.save()
            selected_stream = form.cleaned_data.get('stream')

            UserProfile.objects.create(
                user=user,
                stream=selected_stream
            )

            return redirect('login_page')

    else:
        form = StudentRegisterationForm()

    return render(
        request,
        'zehnify/signup.html',
        {'form': form}
    )


@login_required
def home(request):
    profile, created = UserProfile.objects.get_or_create(
        user=request.user
    )

    try:
        user_stream = request.user.userprofile.stream
    except UserProfile.DoesNotExist:
        user_stream = 'BOTH'

    subjects = Subject.objects.filter(
        stream__in=[user_stream, 'BOTH']
    )

    subject_data = []

    for subject in subjects:

        subject_chapters = subject.chapters.all()

        total_possible_weight = 0
        total_calculated_weight = 0

        for chapter in subject_chapters:

            total_possible_weight += chapter.weightage

            mastery_record = Userchaptermastery.objects.filter(
                user=request.user,
                chapter=chapter
            ).first()

            percentage = (
                mastery_record.percentage
                if mastery_record
                else 0
            )

            total_calculated_weight += (
                percentage * chapter.weightage
            )

        subject_mastery = (
            round(
                total_calculated_weight /
                total_possible_weight
            )
            if total_possible_weight > 0
            else 0
        )

        subject_data.append({
            'subject': subject,
            'subject_mastery': subject_mastery
        })

    streak = get_user_streak(request.user)

    context = {
        'subject_data': subject_data,
        'subjects': subjects,
        'streak': streak
    }

    return render(
        request,
        'zehnify/home.html',
        context
    )


@login_required
def sub_details(request, subject_id):

    try:
        user_stream = request.user.userprofile.stream
    except UserProfile.DoesNotExist:
        user_stream = 'BOTH'

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        stream__in=[user_stream, 'BOTH']
    )

    chapters_11th = Chapter.objects.filter(
        subject=subject,
        grade=11
    )

    chapters_12th = Chapter.objects.filter(
        subject=subject,
        grade=12
    )

    return render(
        request,
        'zehnify/subject_detail.html',
        {
            'subject': subject,
            'chapters_11th': chapters_11th,
            'chapters_12th': chapters_12th,
        }
    )


@login_required
def chapterdetail(request, chapter_id):

    chapter = get_object_or_404(
        Chapter,
        id=chapter_id
    )

    mastery_record = Userchaptermastery.objects.filter(
        user=request.user,
        chapter=chapter
    ).first()

    mastery = (
        mastery_record.percentage
        if mastery_record
        else 0
    )

    latest_attempt = ExamAttempt.objects.filter(
        user=request.user,
        chapter=chapter
    ).order_by(
        '-date_taken'
    ).first()

    mistake_count = MCQAttempt.objects.filter(
        user=request.user,
        mcq__chapter=chapter,
        mcq__is_exam_question=False,
        is_bookmarked=True,
    ).count()

    return render(
        request,
        'zehnify/chapter_detail.html',
        {
            'chapter': chapter,
            'mastery': mastery,
            'mastery_width': f"{mastery}%",
            'latest_attempt': latest_attempt,
            'mistake_count': mistake_count,
        }
    )


# ---------------------------------------------------------------------------
# LEARN
# ---------------------------------------------------------------------------

@login_required
def learn(request, chapter_id):

    chapter = get_object_or_404(
        Chapter,
        id=chapter_id
    )

    subtopics = get_chapter_subtopics(
        chapter
    )

    mastery_data = get_user_subtopic_mastery(
        request.user,
        chapter
    )

    subtopic_data = []

    for subtopic in subtopics:

        data = mastery_data.get(
            subtopic,
            {
                'mastery': None,
                'source': None,
                'practice_percentage': None,
                'practice_score': 0,
                'practice_total': 0,
                'exam_percentage': None,
                'exam_score': 0,
                'exam_total': 0,
            }
        )

        video_count = ChapterVideo.objects.filter(
            chapter=chapter,
            subtopic=subtopic,
        ).count()

        subtopic_data.append({
            'name': subtopic,

            'mastery': data['mastery'],
            'source': data['source'],

            'practice_percentage': data['practice_percentage'],
            'practice_score': data['practice_score'],
            'practice_total': data['practice_total'],

            'exam_percentage': data['exam_percentage'],
            'exam_score': data['exam_score'],
            'exam_total': data['exam_total'],

            'video_count': video_count,
        })

    return render(
        request,
        'zehnify/learn.html',
        {
            'chapter': chapter,
            'subtopic_data': subtopic_data,
        }
    )


@login_required
def learn_subtopic(
    request,
    chapter_id,
    subtopic
):

    chapter = get_object_or_404(
        Chapter,
        id=chapter_id
    )

    lectures = ChapterVideo.objects.filter(
        chapter=chapter,
        subtopic=subtopic,
    )

    watched_ids = set(
        VideoProgress.objects.filter(
            user=request.user,
            video__chapter=chapter,
        ).values_list(
            'video_id',
            flat=True
        )
    )

    practice_count = MCQ.objects.filter(
        chapter=chapter,
        subtopic=subtopic,
        is_exam_question=False,
    ).count()

    return render(
        request,
        'zehnify/learn_subtopic.html',
        {
            'chapter': chapter,
            'subtopic': subtopic,
            'lectures': lectures,
            'watched_ids': watched_ids,
            'practice_count': practice_count,
        }
    )


@login_required
def learn_subtopic_practice(
    request,
    chapter_id,
    subtopic
):

    chapter = get_object_or_404(
        Chapter,
        id=chapter_id
    )

    # -----------------------------------------------------------------------
    # The question IDs are stored in the user's session so the same 20
    # questions shown on GET are used when the form is submitted.
    # -----------------------------------------------------------------------

    session_key = (
        f'learn_practice_'
        f'{chapter.id}_'
        f'{quote(subtopic, safe="")}'
    )

    question_queryset = MCQ.objects.filter(
        chapter=chapter,
        subtopic=subtopic,
        is_exam_question=False,
    )

    available_count = question_queryset.count()

    if available_count < 20:

        request.session.pop(
            session_key,
            None
        )

        return render(
            request,
            'zehnify/learn_subtopic_practice.html',
            {
                'chapter': chapter,
                'subtopic': subtopic,
                'questions': [],
                'error': (
                    f'This sub-topic currently has only '
                    f'{available_count} practice questions. '
                    f'A full 20-question practice set '
                    f'is required.'
                ),
            }
        )

    # -----------------------------------------------------------------------
    # GET
    #
    # Create one random 20-question set and store its IDs in the session.
    # -----------------------------------------------------------------------

    if request.method == 'GET':

        questions = random.sample(
            list(question_queryset),
            20
        )

        request.session[session_key] = [
            question.id
            for question in questions
        ]

        return render(
            request,
            'zehnify/learn_subtopic_practice.html',
            {
                'chapter': chapter,
                'subtopic': subtopic,
                'questions': questions,
            }
        )

    # -----------------------------------------------------------------------
    # POST
    #
    # Retrieve the exact same 20 questions that were displayed on GET.
    # -----------------------------------------------------------------------

    question_ids = request.session.get(
        session_key
    )

    if not question_ids or len(question_ids) != 20:

        return render(
            request,
            'zehnify/learn_subtopic_practice.html',
            {
                'chapter': chapter,
                'subtopic': subtopic,
                'questions': [],
                'error': (
                    'This practice session has expired. '
                    'Please start the practice set again.'
                ),
            }
        )

    questions_by_id = {
        question.id: question
        for question in question_queryset.filter(
            id__in=question_ids
        )
    }

    questions = [
        questions_by_id[question_id]
        for question_id in question_ids
        if question_id in questions_by_id
    ]

    if len(questions) != 20:

        request.session.pop(
            session_key,
            None
        )

        return render(
            request,
            'zehnify/learn_subtopic_practice.html',
            {
                'chapter': chapter,
                'subtopic': subtopic,
                'questions': [],
                'error': (
                    'Some questions in this practice session '
                    'are no longer available. Please start '
                    'the practice set again.'
                ),
            }
        )

    # -----------------------------------------------------------------------
    # Score the exact 20-question set.
    #
    # Unanswered questions count as incorrect.
    # -----------------------------------------------------------------------

    score = 0

    for question in questions:

        selected_option = request.POST.get(
            f'Q{question.id}'
        )

        is_correct = (
            selected_option ==
            question.correct_option
        )

        if is_correct:
            score += 1

        # Keep the existing MCQAttempt system updated so the question's
        # current practice state is also reflected elsewhere in Zehnify.
        if selected_option:

            attempt, created = (
                MCQAttempt.objects.get_or_create(
                    user=request.user,
                    mcq=question,
                )
            )

            attempt.selected_option = selected_option
            attempt.is_correct = is_correct

            # A wrong answer puts the question in the My Mistakes log.
            # A correct answer never removes it - the student discards
            # questions manually from the My Mistakes page.
            if not is_correct:
                attempt.is_bookmarked = True

            attempt.save()

    total_questions = 20

    percentage = round(
        (score / total_questions) * 100
    )

    # -----------------------------------------------------------------------
    # A completed 20-question subtopic practice set becomes an actual
    # mastery checkpoint.
    # -----------------------------------------------------------------------

    SubtopicPracticeAttempt.objects.create(
        user=request.user,
        chapter=chapter,
        subtopic=subtopic,
        score=score,
        total_questions=total_questions,
        percentage=percentage,
    )

    # The session key is removed so opening the practice page again creates
    # a fresh random 20-question set.
    request.session.pop(
        session_key,
        None
    )

    return redirect(
        'learn_subtopic',
        chapter_id=chapter.id,
        subtopic=subtopic,
    )


# ---------------------------------------------------------------------------
# MY MISTAKES
#
# The log is simply MCQAttempt rows with is_bookmarked=True. Sub-topic
# practice and Mixed Practice put questions in; Chapter Exam never does.
# ---------------------------------------------------------------------------

def _option_letter(mcq, value):
    """
    Normalise a stored option (a letter like 'B', or the option's text) to
    'A'/'B'/'C'/'D'. Returns '' if it can't be matched.
    """
    value = (value or '').strip()

    if not value:
        return ''

    if len(value) == 1 and value.upper() in 'ABCD':
        return value.upper()

    lowered = value.casefold()

    for letter in 'ABCD':
        if (getattr(mcq, letter) or '').strip().casefold() == lowered:
            return letter

    return ''


def _mistakes_redirect(chapter_id, subtopic='', mcq_id=None):
    url = reverse(
        'my_mistakes_page',
        kwargs={'chapter_id': chapter_id}
    )

    if subtopic:
        url += '?' + urlencode({'subtopic': subtopic})

    if mcq_id:
        url += f'#mcq-{mcq_id}'

    return redirect(url)


@login_required
def my_mistakes(request, chapter_id):

    chapter = get_object_or_404(
        Chapter,
        id=chapter_id
    )

    # Safety net: exam questions can never appear here, even if one were
    # ever bookmarked by mistake.
    log_queryset = (
        MCQAttempt.objects
        .filter(
            user=request.user,
            mcq__chapter=chapter,
            mcq__is_exam_question=False,
            is_bookmarked=True,
        )
        .select_related('mcq')
    )

    # -----------------------------------------------------------------------
    # POST: save type + reflection, or discard from the log
    # -----------------------------------------------------------------------

    if request.method == 'POST':

        subtopic_filter = request.POST.get('subtopic', '')
        action = request.POST.get('action', 'save')

        try:
            mcq_id = int(request.POST.get('mcq_id', ''))
        except (TypeError, ValueError):
            messages.error(request, 'That question could not be found.')
            return _mistakes_redirect(chapter.id, subtopic_filter)

        attempt = log_queryset.filter(mcq_id=mcq_id).first()

        if attempt is None:
            messages.error(
                request,
                'That question is no longer in your mistakes log.'
            )
            return _mistakes_redirect(chapter.id, subtopic_filter)

        if action == 'discard':

            # Clear the type and reflection too, so if the student misses
            # this question again later it comes back as a fresh mistake.
            attempt.is_bookmarked = False
            attempt.mistake_type = ''
            attempt.reflection = ''

            # update_fields keeps last_attempted (and so the streak)
            # untouched - managing the log is not a practice attempt.
            attempt.save(
                update_fields=[
                    'is_bookmarked',
                    'mistake_type',
                    'reflection',
                ]
            )

            messages.success(
                request,
                'Question removed from your mistakes log.'
            )

            return _mistakes_redirect(chapter.id, subtopic_filter)

        # action == 'save'
        mistake_type = request.POST.get('mistake_type', '').strip()

        # Collapse stray whitespace/newlines into single spaces.
        reflection = ' '.join(
            request.POST.get('reflection', '').split()
        )

        if mistake_type and mistake_type not in MISTAKE_TYPES:
            messages.error(request, 'Please choose a valid mistake type.')
            return _mistakes_redirect(
                chapter.id, subtopic_filter, mcq_id
            )

        if len(reflection.split()) > REFLECTION_MAX_WORDS:
            messages.error(
                request,
                f'Your reflection must be {REFLECTION_MAX_WORDS} '
                f'words or fewer.'
            )
            return _mistakes_redirect(
                chapter.id, subtopic_filter, mcq_id
            )

        if len(reflection) > REFLECTION_MAX_CHARS:
            messages.error(
                request,
                'Your reflection is too long. Please shorten it.'
            )
            return _mistakes_redirect(
                chapter.id, subtopic_filter, mcq_id
            )

        attempt.mistake_type = mistake_type
        attempt.reflection = reflection

        attempt.save(
            update_fields=['mistake_type', 'reflection']
        )

        messages.success(request, 'Saved.')

        return _mistakes_redirect(chapter.id, subtopic_filter, mcq_id)

    # -----------------------------------------------------------------------
    # GET: list mistakes, optionally filtered by sub-topic
    # -----------------------------------------------------------------------

    total_count = log_queryset.count()

    subtopics = [
        s for s in
        log_queryset
        .values_list('mcq__subtopic', flat=True)
        .distinct()
        .order_by('mcq__subtopic')
        if s
    ]

    selected_subtopic = request.GET.get('subtopic', '')

    # Ignore a stale filter (e.g. its last question was just discarded).
    if selected_subtopic not in subtopics:
        selected_subtopic = ''

    attempts = log_queryset

    if selected_subtopic:
        attempts = attempts.filter(mcq__subtopic=selected_subtopic)

    attempts = attempts.order_by('-last_attempted', '-id')

    entries = []

    for attempt in attempts:

        mcq = attempt.mcq

        correct_letter = _option_letter(mcq, mcq.correct_option)
        selected_letter = _option_letter(mcq, attempt.selected_option)

        options = [
            {
                'letter': letter,
                'text': getattr(mcq, letter),
                'is_correct': letter == correct_letter,
                'is_selected': letter == selected_letter,
            }
            for letter in 'ABCD'
        ]

        entries.append({
            'attempt': attempt,
            'mcq': mcq,
            'options': options,
            'correct_letter': correct_letter,
            'selected_letter': selected_letter,
            'answered_correctly_since': (
                bool(correct_letter)
                and correct_letter == selected_letter
            ),
            'old_mistake_type': (
                attempt.mistake_type
                if attempt.mistake_type
                and attempt.mistake_type not in MISTAKE_TYPES
                else ''
            ),
        })

    return render(
        request,
        'zehnify/my_mistakes.html',
        {
            'chapter': chapter,
            'entries': entries,
            'subtopics': subtopics,
            'selected_subtopic': selected_subtopic,
            'mistake_types': MISTAKE_TYPES,
            'total_count': total_count,
            'shown_count': len(entries),
            'reflection_max_words': REFLECTION_MAX_WORDS,
            'reflection_max_chars': REFLECTION_MAX_CHARS,
        }
    )


# ---------------------------------------------------------------------------
# NOTES
# ---------------------------------------------------------------------------

@login_required
def notes(request, chapter_id):

    chapter = get_object_or_404(
        Chapter,
        id=chapter_id
    )

    note, created = ChapterNote.objects.get_or_create(
        user=request.user,
        chapter=chapter
    )

    if request.method == 'POST':

        note.formulas = request.POST.get(
            'formulas',
            ''
        )

        note.reminders = request.POST.get(
            'reminders',
            ''
        )

        note.goals = request.POST.get(
            'goals',
            ''
        )

        note.save()

        return redirect(
            'notes_page',
            chapter_id=chapter.id
        )

    return render(
        request,
        'zehnify/notes.html',
        {
            'chapter': chapter,
            'note': note
        }
    )


# ---------------------------------------------------------------------------
# WATCH LECTURE
# ---------------------------------------------------------------------------

@login_required
def watch_lecture(request, video_id):

    lecture = get_object_or_404(
        ChapterVideo,
        pk=video_id
    )

    return render(
        request,
        'zehnify/watch_lecture.html',
        {
            'lecture': lecture
        }
    )


# ---------------------------------------------------------------------------
# CHAPTER EXAM
# ---------------------------------------------------------------------------

@login_required
def Exam(request, chapter_id):

    chapter = get_object_or_404(
        Chapter,
        id=chapter_id
    )

    mcqs = MCQ.objects.filter(
        chapter=chapter,
        is_exam_question=True
    )

    if request.method == 'POST':

        score = 0

        total = mcqs.count()

        attempt = ExamAttempt.objects.create(
            user=request.user,
            chapter=chapter,
            total_questions=total
        )

        for m in mcqs:

            user_choice = request.POST.get(
                f'Q{m.id}'
            )

            is_correct = (
                user_choice ==
                m.correct_option
            )

            if is_correct:
                score += 1

            UserAnswer.objects.create(
                exam_attempt=attempt,
                mcq=m,
                selected_option=user_choice,
                is_correct=is_correct
            )

        percentage = (
            round((score / total) * 100)
            if total > 0
            else 0
        )

        attempt.score = score
        attempt.percentage = percentage

        attempt.save()

        Userchaptermastery.objects.update_or_create(
            user=request.user,
            chapter=chapter,
            defaults={
                'score': score,
                'percentage': percentage
            }
        )

        return redirect(
            'exam_review',
            chapter_id=chapter.id,
            attempt_id=attempt.id
        )

    return render(
        request,
        'zehnify/exam.html',
        {
            'chapter': chapter,
            'mcqs': mcqs,
            'submitted': False
        }
    )


# ---------------------------------------------------------------------------
# EXAM REVIEW
# ---------------------------------------------------------------------------

@login_required
def exam_review(
    request,
    chapter_id,
    attempt_id
):

    chapter = get_object_or_404(
        Chapter,
        id=chapter_id
    )

    attempt = get_object_or_404(
        ExamAttempt,
        id=attempt_id,
        chapter=chapter,
        user=request.user
    )

    answers = (
        attempt.user_answers
        .select_related('mcq')
        .all()
    )

    subtopic_stats = defaultdict(
        lambda: {
            'wrong': 0,
            'total': 0
        }
    )

    for ans in answers:

        subtopic = (
            ans.mcq.subtopic
            or 'Uncategorized'
        )

        subtopic_stats[subtopic]['total'] += 1

        if not ans.is_correct:
            subtopic_stats[subtopic]['wrong'] += 1

    weakness_list = [
        {
            'subtopic': subtopic,
            'wrong': stats['wrong'],
            'total': stats['total'],
            'incorrect_percentage': (
                round(
                    (stats['wrong'] / stats['total']) * 100
                )
                if stats['total']
                else 0
            ),
        }
        for subtopic, stats
        in subtopic_stats.items()
        if stats['wrong'] > 0
    ]

    weakness_list.sort(
        key=lambda item: (
            item['incorrect_percentage'],
            item['wrong']
        ),
        reverse=True
    )

    return render(
        request,
        'zehnify/exam_review.html',
        {
            'attempt': attempt,
            'answers': answers,
            'weakness_list': weakness_list,
        }
    )


# ---------------------------------------------------------------------------
# VIDEO COMPLETION
# ---------------------------------------------------------------------------

@login_required
@require_POST
def toggle_video_watched(
    request,
    video_id
):

    video = get_object_or_404(
        ChapterVideo,
        pk=video_id
    )

    progress, created = (
        VideoProgress.objects.get_or_create(
            user=request.user,
            video=video
        )
    )

    if not created:
        progress.delete()

    # The old 'video_page' route is retired. Send the student back to the
    # subtopic this lecture belongs to. If a lecture has no subtopic (blank),
    # fall back to the chapter's Learn grid so reverse() can never fail.
    if video.subtopic:

        return redirect(
            'learn_subtopic',
            chapter_id=video.chapter.id,
            subtopic=video.subtopic
        )

    return redirect(
        'learn_page',
        chapter_id=video.chapter.id
    )


# ---------------------------------------------------------------------------
# MIXED PRACTICE
# ---------------------------------------------------------------------------

@login_required
def mixed_practice_setup(
    request,
    chapter_id
):

    chapter = get_object_or_404(
        Chapter,
        id=chapter_id
    )

    subtopics = get_chapter_subtopics(
        chapter
    )

    if request.method == 'POST':

        if not subtopics:

            return render(
                request,
                'zehnify/mixed_practice_setup.html',
                {
                    'chapter': chapter,
                    'subtopics': subtopics,
                    'error': (
                        "This chapter doesn't have any tagged "
                        "sub-topics yet, so Mixed Practice "
                        "isn't available."
                    ),
                }
            )

        try:

            total_requested = int(
                request.POST.get(
                    'total_questions',
                    20
                )
            )

        except (
            TypeError,
            ValueError
        ):

            total_requested = 20

        total_requested = max(
            1,
            min(
                total_requested,
                100
            )
        )

        n = len(subtopics)

        base = total_requested // n

        remainder = total_requested % n

        selected_mcqs = []

        shortages = []

        for i, s in enumerate(subtopics):

            count = (
                base +
                (1 if i < remainder else 0)
            )

            if count == 0:
                continue

            sample = get_subtopic_sample(
                chapter,
                s,
                count
            )

            selected_mcqs.extend(
                sample
            )

            if len(sample) < count:

                shortages.append(
                    f"{s} ({len(sample)}/{count})"
                )

        random.shuffle(
            selected_mcqs
        )

        if not selected_mcqs:

            return render(
                request,
                'zehnify/mixed_practice_setup.html',
                {
                    'chapter': chapter,
                    'subtopics': subtopics,
                    'error': (
                        "No practice questions are "
                        "available to build a session right now."
                    ),
                }
            )

        attempt = MixedPracticeAttempt.objects.create(
            user=request.user,
            chapter=chapter,
            total_questions=len(
                selected_mcqs
            ),
        )

        MixedPracticeAnswer.objects.bulk_create([
            MixedPracticeAnswer(
                attempt=attempt,
                mcq=mcq,
                order=i + 1
            )
            for i, mcq
            in enumerate(selected_mcqs)
        ])

        if shortages:

            request.session[
                'mixed_practice_shortage_notice'
            ] = (
                f"Requested {total_requested} questions, "
                f"built {len(selected_mcqs)} "
                f"(short on: {', '.join(shortages)})."
            )

        return redirect(
            'mixed_practice_session',
            attempt_id=attempt.id
        )

    return render(
        request,
        'zehnify/mixed_practice_setup.html',
        {
            'chapter': chapter,
            'subtopics': subtopics
        }
    )


@login_required
def mixed_practice_session(
    request,
    attempt_id
):

    attempt = get_object_or_404(
        MixedPracticeAttempt,
        id=attempt_id,
        user=request.user
    )

    answers = (
        attempt.answers
        .select_related('mcq')
        .order_by('order')
    )

    if request.method == 'POST':

        score = 0

        for ans in answers:

            user_choice = request.POST.get(
                f'Q{ans.mcq.id}'
            )

            is_correct = (
                user_choice ==
                ans.mcq.correct_option
            )

            ans.selected_option = user_choice
            ans.is_correct = is_correct

            ans.save()

            if is_correct:
                score += 1

            # A wrong answer puts the question in the My Mistakes log.
            # This only touches MCQAttempt. It does NOT write to
            # SubtopicPracticeAttempt, get_user_subtopic_mastery or
            # Userchaptermastery - Mixed Practice never counts toward mastery.
            if user_choice and not is_correct:

                mcq_attempt, created = (
                    MCQAttempt.objects.get_or_create(
                        user=request.user,
                        mcq=ans.mcq,
                    )
                )

                mcq_attempt.selected_option = user_choice
                mcq_attempt.is_correct = False
                mcq_attempt.is_bookmarked = True

                mcq_attempt.save()

        total = answers.count()

        percentage = (
            round((score / total) * 100)
            if total > 0
            else 0
        )

        attempt.score = score
        attempt.percentage = percentage

        attempt.save()

        return redirect(
            'mixed_practice_review',
            attempt_id=attempt.id
        )

    shortage_notice = request.session.pop(
        'mixed_practice_shortage_notice',
        None
    )

    return render(
        request,
        'zehnify/mixed_practice_session.html',
        {
            'chapter': attempt.chapter,
            'attempt': attempt,
            'answers': answers,
            'shortage_notice': shortage_notice,
        }
    )


@login_required
def mixed_practice_review(
    request,
    attempt_id
):

    attempt = get_object_or_404(
        MixedPracticeAttempt,
        id=attempt_id,
        user=request.user
    )

    answers = (
        attempt.answers
        .select_related('mcq')
        .order_by('order')
    )

    subtopic_stats = defaultdict(
        lambda: {
            'wrong': 0,
            'total': 0
        }
    )

    for ans in answers:

        s = (
            ans.mcq.subtopic
            or 'Uncategorized'
        )

        subtopic_stats[s]['total'] += 1

        if not ans.is_correct:
            subtopic_stats[s]['wrong'] += 1

    weakness_list = [
        {
            'subtopic': k,
            'wrong': v['wrong'],
            'total': v['total']
        }
        for k, v
        in subtopic_stats.items()
        if v['wrong'] > 0
    ]

    weakness_list.sort(
        key=lambda x: x['wrong'],
        reverse=True
    )

    return render(
        request,
        'zehnify/mixed_practice_review.html',
        {
            'attempt': attempt,
            'answers': answers,
            'weakness_list': weakness_list,
        }
    )