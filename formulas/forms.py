from django import forms
from django.core.exceptions import ValidationError
from .models import (
    Formula, Ingredient, Literature, SafetyReview,
    LiteratureAttachment, UserProfile, RiskAlert,
    OperationLog, FormulaVersion,
    AcademicAnnotation, AnnotationEditHistory,
    Dispute, DisputeArgument, DisputeProgress,
)


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


class LiteratureAttachmentForm(forms.ModelForm):
    class Meta:
        model = LiteratureAttachment
        fields = ['file', 'file_name', 'file_type', 'description', 'page_reference']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'file_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '可选，默认使用文件名'}),
            'file_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '文件内容说明'}),
            'page_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '如：第15-20页'}),
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
    change_note = forms.CharField(
        required=False,
        label='版本变更说明',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': '可选，记录本次修改的主要内容',
        }),
    )

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
    USAGE_CHOICES = [('', '全部用途')] + list(Formula._meta.get_field('usage_category').choices)
    SAFETY_CHOICES = [('', '全部等级')] + list(Formula._meta.get_field('safety_level').choices)
    REVIEW_CHOICES = [('', '全部状态')] + list(Formula._meta.get_field('review_status').choices)
    ARCHIVE_CHOICES = [('', '全部归档状态')] + list(Formula._meta.get_field('archive_status').choices)

    era = forms.CharField(
        required=False,
        label='年代',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '如宋代、明代、清代等'}),
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
    archive_status = forms.ChoiceField(
        choices=ARCHIVE_CHOICES,
        required=False,
        label='归档状态',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    keyword = forms.CharField(
        required=False,
        label='关键词',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '搜索配方名称、编号、别名'}),
    )


class AdvancedSearchForm(forms.Form):
    formula_no = forms.CharField(
        required=False,
        label='配方编号',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '精确或模糊匹配'}),
    )
    name = forms.CharField(
        required=False,
        label='配方名称',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    alias = forms.CharField(
        required=False,
        label='别名',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    ingredient_name = forms.CharField(
        required=False,
        label='成分名称',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '包含某成分的配方'}),
    )
    ingredient_percentage_min = forms.FloatField(
        required=False,
        label='成分占比最小值(%)',
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
    ingredient_percentage_max = forms.FloatField(
        required=False,
        label='成分占比最大值(%)',
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
    literature_title = forms.CharField(
        required=False,
        label='文献标题',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    author = forms.CharField(
        required=False,
        label='文献作者',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    dynasty = forms.CharField(
        required=False,
        label='朝代',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    publication_year_min = forms.IntegerField(
        required=False,
        label='最早年份',
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    publication_year_max = forms.IntegerField(
        required=False,
        label='最晚年份',
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    region = forms.CharField(
        required=False,
        label='来源地区',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    usage_category = forms.ChoiceField(
        choices=[('', '全部用途')] + list(Formula._meta.get_field('usage_category').choices),
        required=False,
        label='用途分类',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    safety_level = forms.ChoiceField(
        choices=[('', '全部等级')] + list(Formula._meta.get_field('safety_level').choices),
        required=False,
        label='安全等级',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    review_status = forms.ChoiceField(
        choices=[('', '全部状态')] + list(Formula._meta.get_field('review_status').choices),
        required=False,
        label='评审状态',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    risk_score_min = forms.IntegerField(
        required=False,
        label='风险分值最小值',
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    risk_score_max = forms.IntegerField(
        required=False,
        label='风险分值最大值',
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    created_by = forms.CharField(
        required=False,
        label='创建人',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    search_mode = forms.ChoiceField(
        choices=[
            ('and', '所有条件同时满足(AND)'),
            ('or', '任意条件满足(OR)'),
        ],
        required=False,
        initial='and',
        label='检索模式',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )


class FormulaCompareForm(forms.Form):
    formula_a = forms.ModelChoiceField(
        queryset=Formula.objects.all(),
        label='配方 A',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    version_a = forms.IntegerField(
        required=False,
        label='配方 A 版本(留空为最新版)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
    )
    formula_b = forms.ModelChoiceField(
        queryset=Formula.objects.all(),
        label='配方 B',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    version_b = forms.IntegerField(
        required=False,
        label='配方 B 版本(留空为最新版)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        fa = cleaned_data.get('formula_a')
        fb = cleaned_data.get('formula_b')
        va = cleaned_data.get('version_a')
        vb = cleaned_data.get('version_b')
        if fa and fb and fa.pk == fb.pk and (not va or not vb or va == vb):
            raise ValidationError('请选择不同的配方或不同版本进行对比')
        return cleaned_data


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['role', 'department', 'phone', 'bio']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class AlertHandleForm(forms.ModelForm):
    class Meta:
        model = RiskAlert
        fields = ['status', 'handle_note']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'handle_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class OperationLogFilterForm(forms.Form):
    OPERATION_CHOICES = [('', '全部操作')] + OperationLog._meta.get_field('operation_type').choices

    user = forms.CharField(
        required=False,
        label='操作用户',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '用户名'}),
    )
    operation_type = forms.ChoiceField(
        choices=OPERATION_CHOICES,
        required=False,
        label='操作类型',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    target_model = forms.CharField(
        required=False,
        label='对象类型',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '如Formula、Literature'}),
    )
    target_name = forms.CharField(
        required=False,
        label='对象名称',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    date_from = forms.DateField(
        required=False,
        label='起始日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    date_to = forms.DateField(
        required=False,
        label='结束日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )


class DataExportForm(forms.Form):
    EXPORT_FORMAT_CHOICES = [
        ('csv', 'CSV 格式'),
        ('json', 'JSON 格式'),
    ]
    EXPORT_TARGET_CHOICES = [
        ('formulas', '配方数据(含成分)'),
        ('formulas_basic', '配方数据(基本信息)'),
        ('literatures', '文献数据'),
        ('ingredients', '成分统计数据'),
        ('reviews', '评审记录'),
        ('operation_logs', '操作日志(仅管理员/审计员)'),
    ]

    export_target = forms.ChoiceField(
        choices=EXPORT_TARGET_CHOICES,
        label='导出内容',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    export_format = forms.ChoiceField(
        choices=EXPORT_FORMAT_CHOICES,
        label='导出格式',
        initial='csv',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    include_attachments = forms.BooleanField(
        required=False,
        label='包含文献附件信息',
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    date_from = forms.DateField(
        required=False,
        label='数据起始日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    date_to = forms.DateField(
        required=False,
        label='数据结束日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )


class LiteratureFilterForm(forms.Form):
    SOURCE_CHOICES = [('', '全部类型')] + list(Literature._meta.get_field('source_type').choices)

    keyword = forms.CharField(
        required=False,
        label='关键词',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '标题、作者、索书号'}),
    )
    source_type = forms.ChoiceField(
        choices=SOURCE_CHOICES,
        required=False,
        label='文献类型',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    dynasty = forms.CharField(
        required=False,
        label='朝代',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    author = forms.CharField(
        required=False,
        label='作者',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )


class AcademicAnnotationForm(forms.ModelForm):
    class Meta:
        model = AcademicAnnotation
        fields = [
            'content_type', 'formula', 'literature',
            'annotation_type', 'title', 'content',
            'reference', 'reference_page',
        ]
        widgets = {
            'content_type': forms.Select(attrs={'class': 'form-control'}),
            'formula': forms.Select(attrs={'class': 'form-control'}),
            'literature': forms.Select(attrs={'class': 'form-control'}),
            'annotation_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '简明概括注释主题'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': '详细阐述注释内容'}),
            'reference': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '引用的文献、版本或其他学术来源'}),
            'reference_page': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '如：第15-20页、卷三'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        content_type = cleaned_data.get('content_type')
        formula = cleaned_data.get('formula')
        literature = cleaned_data.get('literature')
        if content_type == 'formula' and not formula:
            raise ValidationError('配方类型注释必须选择关联配方')
        if content_type == 'literature' and not literature:
            raise ValidationError('文献类型注释必须选择关联文献')
        return cleaned_data


class AcademicAnnotationFilterForm(forms.Form):
    ANNOTATION_TYPE_CHOICES_FILTER = [('', '全部类型')] + list(
        AcademicAnnotation._meta.get_field('annotation_type').choices
    )
    CONTENT_TYPE_CHOICES_FILTER = [('', '全部对象')] + list(
        AcademicAnnotation._meta.get_field('content_type').choices
    )

    annotation_type = forms.ChoiceField(
        choices=ANNOTATION_TYPE_CHOICES_FILTER,
        required=False,
        label='注释类型',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    content_type = forms.ChoiceField(
        choices=CONTENT_TYPE_CHOICES_FILTER,
        required=False,
        label='注释对象',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    keyword = forms.CharField(
        required=False,
        label='关键词',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '搜索标题、内容或依据文献'}),
    )


class DisputeForm(forms.ModelForm):
    class Meta:
        model = Dispute
        fields = [
            'formula', 'literature', 'dispute_type',
            'title', 'description',
        ]
        widgets = {
            'formula': forms.Select(attrs={'class': 'form-control'}),
            'literature': forms.Select(attrs={'class': 'form-control'}),
            'dispute_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '简明概括争议主题'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': '详细描述争议问题'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        formula = cleaned_data.get('formula')
        literature = cleaned_data.get('literature')
        if not formula and not literature:
            raise ValidationError('争议必须关联配方或文献')
        return cleaned_data


class DisputeArgumentForm(forms.ModelForm):
    class Meta:
        model = DisputeArgument
        fields = ['stance', 'viewpoint', 'evidence', 'evidence_reference']
        widgets = {
            'stance': forms.Select(attrs={'class': 'form-control'}),
            'viewpoint': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '阐述您的学术观点'}),
            'evidence': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '支持此观点的证据材料'}),
            'evidence_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '证据出处，如文献标题、页码等'}),
        }


class DisputeProgressForm(forms.ModelForm):
    class Meta:
        model = DisputeProgress
        fields = ['new_status', 'comment']
        widgets = {
            'new_status': forms.Select(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '状态变更说明'}),
        }


class DisputeFilterForm(forms.Form):
    DISPUTE_TYPE_CHOICES_FILTER = [('', '全部类型')] + list(
        Dispute._meta.get_field('dispute_type').choices
    )
    DISPUTE_STATUS_CHOICES_FILTER = [('', '全部状态')] + list(
        Dispute._meta.get_field('status').choices
    )

    dispute_type = forms.ChoiceField(
        choices=DISPUTE_TYPE_CHOICES_FILTER,
        required=False,
        label='争议类型',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    status = forms.ChoiceField(
        choices=DISPUTE_STATUS_CHOICES_FILTER,
        required=False,
        label='处理状态',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    literature_source = forms.CharField(
        required=False,
        label='文献来源',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '搜索关联文献标题'}),
    )
    keyword = forms.CharField(
        required=False,
        label='关键词',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '搜索争议标题或描述'}),
    )


class AnnotationEditForm(forms.ModelForm):
    edit_reason = forms.CharField(
        required=False,
        label='修改原因',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '说明本次修改原因'}),
    )

    class Meta:
        model = AcademicAnnotation
        fields = ['title', 'content', 'reference', 'reference_page']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'reference': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'reference_page': forms.TextInput(attrs={'class': 'form-control'}),
        }


class DisputeConclusionForm(forms.ModelForm):
    class Meta:
        model = Dispute
        fields = ['status', 'conclusion']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'conclusion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '填写争议结论'}),
        }
