from django import forms
from django.core.exceptions import ValidationError
from .models import Formula, Ingredient, Literature, SafetyReview


class LiteratureForm(forms.ModelForm):
    class Meta:
        model = Literature
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
            'publication_year': forms.NumberInput(attrs={'class': 'form-control'}),
            'dynasty': forms.TextInput(attrs={'class': 'form-control'}),
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'publisher': forms.TextInput(attrs={'class': 'form-control'}),
            'call_number': forms.TextInput(attrs={'class': 'form-control'}),
            'source_type': forms.Select(attrs={'class': 'form-control'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ['name', 'chinese_name', 'percentage', 'remark']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'chinese_name': forms.TextInput(attrs={'class': 'form-control'}),
            'percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'remark': forms.TextInput(attrs={'class': 'form-control'}),
        }


IngredientFormSet = forms.inlineformset_factory(
    Formula,
    Ingredient,
    form=IngredientForm,
    extra=3,
    can_delete=True,
)


class FormulaForm(forms.ModelForm):
    class Meta:
        model = Formula
        fields = [
            'formula_no', 'name', 'alias', 'literature', 'literature_page',
            'era', 'era_year', 'region', 'usage_category', 'description',
            'safety_level', 'safety_note', 'review_status', 'archive_status',
        ]
        widgets = {
            'formula_no': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'alias': forms.TextInput(attrs={'class': 'form-control'}),
            'literature': forms.Select(attrs={'class': 'form-control'}),
            'literature_page': forms.TextInput(attrs={'class': 'form-control'}),
            'era': forms.TextInput(attrs={'class': 'form-control'}),
            'era_year': forms.NumberInput(attrs={'class': 'form-control'}),
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'usage_category': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'safety_level': forms.Select(attrs={'class': 'form-control'}),
            'safety_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'review_status': forms.Select(attrs={'class': 'form-control'}),
            'archive_status': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


class SafetyReviewForm(forms.ModelForm):
    class Meta:
        model = SafetyReview
        fields = ['review_result', 'opinion', 'risk_analysis']
        widgets = {
            'review_result': forms.Select(attrs={'class': 'form-control'}),
            'opinion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'risk_analysis': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class FormulaFilterForm(forms.Form):
    ERA_CHOICES = [
        ('', '全部年代'),
        ('tang', '唐代'),
        ('song', '宋代'),
        ('yuan', '元代'),
        ('ming', '明代'),
        ('qing', '清代'),
        ('modern', '近代'),
    ]

    USAGE_CHOICES = [('', '全部用途')] + list(Formula._meta.get_field('usage_category').choices)
    SAFETY_CHOICES = [('', '全部等级')] + list(Formula._meta.get_field('safety_level').choices)
    REVIEW_CHOICES = [('', '全部状态')] + list(Formula._meta.get_field('review_status').choices)

    era = forms.ChoiceField(
        choices=ERA_CHOICES,
        required=False,
        label='年代',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    region = forms.CharField(
        required=False,
        label='来源地区',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '输入地区关键词'}),
    )
    usage_category = forms.ChoiceField(
        choices=USAGE_CHOICES,
        required=False,
        label='用途分类',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    safety_level = forms.ChoiceField(
        choices=SAFETY_CHOICES,
        required=False,
        label='安全等级',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    review_status = forms.ChoiceField(
        choices=REVIEW_CHOICES,
        required=False,
        label='评审状态',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    keyword = forms.CharField(
        required=False,
        label='关键词',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '搜索配方名称、编号'}),
    )
