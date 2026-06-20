from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from .models import (
    Literature, Formula, Ingredient, SafetyReview,
    UserProfile, OperationLog, FormulaVersion,
    LiteratureAttachment, RiskAlert, ReviewFlow,
    AcademicAnnotation, AnnotationEditHistory,
    Dispute, DisputeArgument, DisputeProgress,
    ResearchTopic, TopicKeyword, TopicReference, TopicEntry, TopicNote,
)


class IngredientInline(admin.TabularInline):
    model = Ingredient
    extra = 3
    fields = ['name', 'chinese_name', 'percentage', 'remark']


class SafetyReviewInline(admin.TabularInline):
    model = SafetyReview
    extra = 1
    fields = ['reviewer', 'review_result', 'opinion', 'reviewed_at']
    readonly_fields = ['reviewed_at']


class LiteratureAttachmentInline(admin.TabularInline):
    model = LiteratureAttachment
    extra = 1
    fields = ['file', 'file_name', 'file_type', 'description', 'page_reference', 'uploaded_by', 'uploaded_at']
    readonly_fields = ['uploaded_at']


class FormulaVersionInline(admin.TabularInline):
    model = FormulaVersion
    extra = 0
    fields = ['version', 'name', 'safety_level', 'created_by', 'created_at', 'change_note']
    readonly_fields = ['version', 'name', 'safety_level', 'created_by', 'created_at', 'ingredients_json']
    can_delete = False


class ReviewFlowInline(admin.TabularInline):
    model = ReviewFlow
    extra = 0
    fields = ['step', 'operator', 'from_status', 'to_status', 'created_at']
    readonly_fields = ['step', 'operator', 'from_status', 'to_status', 'created_at', 'comment']
    can_delete = False


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'department', 'phone', 'created_at']
    list_filter = ['role', 'department']
    search_fields = ['user__username', 'user__email', 'department', 'phone']
    autocomplete_fields = ['user']


@admin.register(Literature)
class LiteratureAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'publication_year', 'dynasty', 'region', 'source_type', 'created_by']
    list_filter = ['source_type', 'dynasty', 'region']
    search_fields = ['title', 'author', 'call_number']
    ordering = ['-publication_year']
    inlines = [LiteratureAttachmentInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(LiteratureAttachment)
class LiteratureAttachmentAdmin(admin.ModelAdmin):
    list_display = ['literature', 'file_name', 'file_type', 'page_reference', 'uploaded_by', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['literature__title', 'file_name', 'description']
    readonly_fields = ['uploaded_at']


class FormulaAdminForm(forms.ModelForm):
    class Meta:
        model = Formula
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


@admin.register(Formula)
class FormulaAdmin(admin.ModelAdmin):
    form = FormulaAdminForm
    inlines = [IngredientInline, SafetyReviewInline, FormulaVersionInline, ReviewFlowInline]
    list_display = [
        'formula_no', 'name', 'era', 'region', 'usage_category',
        'safety_level', 'review_status', 'archive_status', 'version',
        'risk_score_display', 'created_by', 'created_at',
    ]
    list_filter = ['safety_level', 'review_status', 'archive_status', 'usage_category', 'version']
    search_fields = ['formula_no', 'name', 'alias', 'region', 'era']
    readonly_fields = ['created_at', 'updated_at', 'version']
    fieldsets = [
        ('基本信息', {
            'fields': ['formula_no', 'name', 'alias', 'created_by', 'updated_by', 'version']
        }),
        ('文献出处', {
            'fields': ['literature', 'literature_page']
        }),
        ('历史信息', {
            'fields': ['era', 'era_year', 'region', 'usage_category', 'description']
        }),
        ('安全与评审', {
            'fields': ['safety_level', 'safety_note', 'review_status', 'archive_status']
        }),
        ('时间戳', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def risk_score_display(self, obj):
        score = obj.risk_score
        color = 'green' if score < 30 else ('orange' if score < 60 else 'red')
        return f'<span style="color:{color};font-weight:bold;">{score}</span>'
    risk_score_display.short_description = '风险分值'
    risk_score_display.allow_tags = True

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        instance = form.instance
        if instance.pk:
            total = instance.total_percentage
            if instance.ingredients.exists() and abs(total - 100.0) > 0.01:
                raise ValidationError(
                    f'成分比例合计必须等于 100%，当前为 {total}%。请调整成分比例。'
                )


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ['formula', 'name', 'chinese_name', 'percentage']
    list_filter = ['formula']
    search_fields = ['name', 'chinese_name']


@admin.register(FormulaVersion)
class FormulaVersionAdmin(admin.ModelAdmin):
    list_display = ['formula', 'version', 'name', 'safety_level', 'created_by', 'created_at']
    list_filter = ['safety_level', 'created_at']
    search_fields = ['formula__formula_no', 'formula__name', 'name', 'change_note']
    readonly_fields = ['formula', 'version', 'name', 'alias', 'description', 'safety_level',
                       'safety_note', 'ingredients_json', 'created_by', 'created_at']


@admin.register(SafetyReview)
class SafetyReviewAdmin(admin.ModelAdmin):
    list_display = ['formula', 'reviewer', 'review_result', 'reviewed_at']
    list_filter = ['review_result', 'reviewed_at']
    search_fields = ['formula__formula_no', 'formula__name', 'opinion']
    readonly_fields = ['reviewed_at']


@admin.register(ReviewFlow)
class ReviewFlowAdmin(admin.ModelAdmin):
    list_display = ['formula', 'step', 'operator', 'from_status', 'to_status', 'created_at']
    list_filter = ['step', 'created_at']
    search_fields = ['formula__formula_no', 'formula__name', 'comment']
    readonly_fields = ['formula', 'step', 'operator', 'from_status', 'to_status', 'comment', 'created_at']


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'operation_type', 'target_model', 'target_name', 'ip_address']
    list_filter = ['operation_type', 'target_model', 'created_at']
    search_fields = ['user__username', 'target_name', 'target_id', 'description', 'ip_address']
    readonly_fields = ['user', 'operation_type', 'target_model', 'target_id', 'target_name',
                       'description', 'old_value', 'new_value', 'ip_address', 'user_agent', 'created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RiskAlert)
class RiskAlertAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'level', 'alert_type', 'title', 'formula', 'status', 'risk_score']
    list_filter = ['level', 'alert_type', 'status', 'created_at']
    search_fields = ['title', 'message', 'handle_note']
    readonly_fields = ['formula', 'alert_type', 'level', 'title', 'message', 'risk_score',
                       'triggered_by', 'created_at']
    date_hierarchy = 'created_at'
    fieldsets = [
        ('预警信息', {
            'fields': ['level', 'alert_type', 'title', 'message', 'risk_score', 'formula', 'triggered_by', 'created_at']
        }),
        ('处理信息', {
            'fields': ['status', 'handled_by', 'handled_at', 'handle_note']
        }),
    ]


class AnnotationEditHistoryInline(admin.TabularInline):
    model = AnnotationEditHistory
    extra = 0
    fields = ['old_content', 'new_content', 'edit_reason', 'edited_by', 'edited_at']
    readonly_fields = ['old_content', 'new_content', 'edit_reason', 'edited_by', 'edited_at']
    can_delete = False


@admin.register(AcademicAnnotation)
class AcademicAnnotationAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'annotation_type', 'content_type',
        'formula', 'literature', 'created_by', 'created_at',
    ]
    list_filter = ['annotation_type', 'content_type', 'created_at']
    search_fields = ['title', 'content', 'reference']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [AnnotationEditHistoryInline]
    fieldsets = [
        ('关联对象', {
            'fields': ['content_type', 'formula', 'literature']
        }),
        ('注释内容', {
            'fields': ['annotation_type', 'title', 'content', 'reference', 'reference_page']
        }),
        ('元信息', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(AnnotationEditHistory)
class AnnotationEditHistoryAdmin(admin.ModelAdmin):
    list_display = ['annotation', 'edited_by', 'edited_at', 'edit_reason']
    list_filter = ['edited_at']
    search_fields = ['annotation__title', 'old_content', 'new_content']
    readonly_fields = ['annotation', 'old_content', 'new_content', 'edit_reason', 'edited_by', 'edited_at']

    def has_add_permission(self, request):
        return False


class DisputeArgumentInline(admin.TabularInline):
    model = DisputeArgument
    extra = 0
    fields = ['stance', 'viewpoint', 'evidence', 'evidence_reference', 'submitted_by', 'submitted_at']
    readonly_fields = ['submitted_by', 'submitted_at']


class DisputeProgressInline(admin.TabularInline):
    model = DisputeProgress
    extra = 0
    fields = ['old_status', 'new_status', 'comment', 'operator', 'operated_at']
    readonly_fields = ['old_status', 'new_status', 'comment', 'operator', 'operated_at']
    can_delete = False


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'dispute_type', 'status',
        'formula', 'literature', 'initiated_by', 'initiated_at',
    ]
    list_filter = ['dispute_type', 'status', 'initiated_at']
    search_fields = ['title', 'description', 'conclusion']
    readonly_fields = ['initiated_at', 'resolved_at', 'updated_at']
    inlines = [DisputeArgumentInline, DisputeProgressInline]
    fieldsets = [
        ('关联对象', {
            'fields': ['formula', 'literature']
        }),
        ('争议信息', {
            'fields': ['dispute_type', 'title', 'description', 'status', 'conclusion']
        }),
        ('发起与解决', {
            'fields': ['initiated_by', 'initiated_at', 'resolved_by', 'resolved_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(DisputeArgument)
class DisputeArgumentAdmin(admin.ModelAdmin):
    list_display = ['dispute', 'stance', 'submitted_by', 'submitted_at']
    list_filter = ['stance', 'submitted_at']
    search_fields = ['dispute__title', 'viewpoint', 'evidence']
    readonly_fields = ['submitted_at', 'updated_at']


@admin.register(DisputeProgress)
class DisputeProgressAdmin(admin.ModelAdmin):
    list_display = ['dispute', 'old_status', 'new_status', 'operator', 'operated_at']
    list_filter = ['new_status', 'operated_at']
    search_fields = ['dispute__title', 'comment']
    readonly_fields = ['dispute', 'old_status', 'new_status', 'comment', 'operator', 'operated_at']

    def has_add_permission(self, request):
        return False


class TopicKeywordInline(admin.TabularInline):
    model = TopicKeyword
    extra = 2
    fields = ['keyword']


class TopicEntryInline(admin.TabularInline):
    model = TopicEntry
    extra = 1
    fields = ['content_type', 'formula', 'literature', 'annotation', 'dispute', 'review', 'note']
    readonly_fields = ['added_by', 'added_at']


class TopicNoteInline(admin.TabularInline):
    model = TopicNote
    extra = 0
    fields = ['note_type', 'title', 'content', 'created_by']
    readonly_fields = ['created_by', 'created_at']


class TopicReferenceInline(admin.TabularInline):
    model = TopicReference
    extra = 0
    fields = ['title', 'author', 'source', 'url', 'note']
    readonly_fields = ['added_by', 'added_at']


@admin.register(ResearchTopic)
class ResearchTopicAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'status', 'leader', 'created_by', 'created_at']
    list_filter = ['category', 'status', 'created_at']
    search_fields = ['title', 'description', 'research_note']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [TopicKeywordInline, TopicEntryInline, TopicNoteInline, TopicReferenceInline]
    fieldsets = [
        ('基本信息', {
            'fields': ['title', 'description', 'category', 'status', 'leader']
        }),
        ('研究内容', {
            'fields': ['research_note', 'stage_conclusion']
        }),
        ('时间信息', {
            'fields': ['started_at', 'completed_at', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(TopicKeyword)
class TopicKeywordAdmin(admin.ModelAdmin):
    list_display = ['topic', 'keyword']
    search_fields = ['topic__title', 'keyword']


@admin.register(TopicEntry)
class TopicEntryAdmin(admin.ModelAdmin):
    list_display = ['topic', 'content_type', 'formula', 'literature', 'annotation', 'dispute', 'review', 'added_by', 'added_at']
    list_filter = ['content_type', 'added_at']
    search_fields = ['topic__title', 'note']


@admin.register(TopicNote)
class TopicNoteAdmin(admin.ModelAdmin):
    list_display = ['topic', 'note_type', 'title', 'created_by', 'created_at']
    list_filter = ['note_type', 'created_at']
    search_fields = ['topic__title', 'title', 'content']


@admin.register(TopicReference)
class TopicReferenceAdmin(admin.ModelAdmin):
    list_display = ['topic', 'title', 'author', 'source', 'added_by', 'added_at']
    search_fields = ['topic__title', 'title', 'author']
