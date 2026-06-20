from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from .models import Literature, Formula, Ingredient, SafetyReview


class IngredientInline(admin.TabularInline):
    model = Ingredient
    extra = 3
    fields = ['name', 'chinese_name', 'percentage', 'remark']


class SafetyReviewInline(admin.TabularInline):
    model = SafetyReview
    extra = 1
    fields = ['reviewer', 'review_result', 'opinion', 'reviewed_at']
    readonly_fields = ['reviewed_at']


@admin.register(Literature)
class LiteratureAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'publication_year', 'dynasty', 'region', 'source_type']
    list_filter = ['source_type', 'dynasty', 'region']
    search_fields = ['title', 'author', 'call_number']
    ordering = ['-publication_year']


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
    inlines = [IngredientInline, SafetyReviewInline]
    list_display = [
        'formula_no', 'name', 'era', 'region', 'usage_category',
        'safety_level', 'review_status', 'archive_status', 'created_at',
    ]
    list_filter = ['safety_level', 'review_status', 'archive_status', 'usage_category']
    search_fields = ['formula_no', 'name', 'alias', 'region', 'era']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        ('基本信息', {
            'fields': ['formula_no', 'name', 'alias', 'created_by']
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


@admin.register(SafetyReview)
class SafetyReviewAdmin(admin.ModelAdmin):
    list_display = ['formula', 'reviewer', 'review_result', 'reviewed_at']
    list_filter = ['review_result', 'reviewed_at']
    search_fields = ['formula__formula_no', 'formula__name', 'opinion']
