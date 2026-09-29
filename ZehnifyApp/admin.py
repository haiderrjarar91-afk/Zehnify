from django.contrib import admin
from .models import Chapter, ChapterVideo, MCQ, Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'subject')
    list_filter = ('subject',)
    search_fields = ('name', 'subject__name')
    list_select_related = ('subject',)


@admin.register(ChapterVideo)
class ChapterVideoAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'chapter')
    list_filter = ('chapter__subject', 'chapter')
    search_fields = ('title', 'chapter__name')
    list_select_related = ('chapter',)


@admin.register(MCQ)
class MCQAdmin(admin.ModelAdmin):
    # Columns shown in the main table view
    list_display = (
        'id',
        'get_subject',
        'chapter',
        'short_question',
        'correct_option',
        'has_diagram',
        'is_exam_question',
    )

    # Sidebar filters to instantly narrow down results
    list_filter = ('chapter__subject', 'chapter', 'is_exam_question')

    # Instant multi-field search (includes related chapter & subject names)
    search_fields = (
        'question_text',
        'A',
        'B',
        'C',
        'D',
        'master_explanation',
        'chapter__name',
    )

    # SQL Optimization: Prevents N+1 queries by joining related tables in 1 query
    list_select_related = ('chapter', 'chapter__subject')

    # Pagination: Keeps page load lightweight
    list_per_page = 30

    # Custom helper to show short question snippet
    def short_question(self, obj):
        return obj.question_text[:75] + '...' if len(obj.question_text) > 75 else obj.question_text
    short_question.short_description = "Question"

    # Custom helper to display parent subject
    def get_subject(self, obj):
        return obj.chapter.subject.name if obj.chapter and obj.chapter.subject else '-'
    get_subject.short_description = "Subject"
    get_subject.admin_order_field = 'chapter__subject__name'

    # Custom helper indicator for diagram presence
    def has_diagram(self, obj):
        return bool(obj.diagram)
    has_diagram.boolean = True
    has_diagram.short_description = "Diagram?"