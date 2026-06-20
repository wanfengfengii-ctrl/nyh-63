from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth.models import User


SAFETY_LEVEL_CHOICES = [
    ('low', '低风险'),
    ('medium', '中风险'),
    ('high', '高风险'),
]

REVIEW_STATUS_CHOICES = [
    ('draft', '草稿'),
    ('pending', '待评审'),
    ('recheck', '待复核'),
    ('approved', '评审通过'),
    ('rejected', '评审驳回'),
]

ARCHIVE_STATUS_CHOICES = [
    ('active', '在用'),
    ('archived', '已归档'),
]


class Literature(models.Model):
    title = models.CharField('文献标题', max_length=300)
    author = models.CharField('作者/编纂者', max_length=200, blank=True)
    publication_year = models.IntegerField('出版/刊行年代', null=True, blank=True)
    dynasty = models.CharField('朝代/时期', max_length=100, blank=True)
    region = models.CharField('来源地区', max_length=100, blank=True)
    publisher = models.CharField('出版机构/馆藏', max_length=200, blank=True)
    call_number = models.CharField('索书号/编号', max_length=100, blank=True)
    source_type = models.CharField(
        '文献类型',
        max_length=50,
        choices=[
            ('book', '典籍'),
            ('manuscript', '手抄本'),
            ('journal', '期刊论文'),
            ('archive', '档案'),
            ('other', '其他'),
        ],
        default='book',
    )
    remark = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '文献来源'
        verbose_name_plural = '文献来源'
        ordering = ['-publication_year']

    def __str__(self):
        if self.publication_year:
            return f'[{self.publication_year}] {self.title}'
        return self.title


class Formula(models.Model):
    formula_no = models.CharField('配方编号', max_length=50, unique=True)
    name = models.CharField('配方名称', max_length=200)
    alias = models.CharField('别名', max_length=200, blank=True)
    literature = models.ForeignKey(
        Literature,
        on_delete=models.PROTECT,
        verbose_name='文献出处',
        null=True,
        blank=True,
        related_name='formulas',
    )
    literature_page = models.CharField('文献页码/章节', max_length=100, blank=True)
    era = models.CharField('年代', max_length=100, blank=True)
    era_year = models.IntegerField('具体年份', null=True, blank=True)
    region = models.CharField('来源地区', max_length=100, blank=True)
    usage_category = models.CharField(
        '用途分类',
        max_length=50,
        choices=[
            ('military', '军用'),
            ('fireworks', '烟花'),
            ('mining', '采矿'),
            ('signal', '信号'),
            ('medical', '医用'),
            ('other', '其他'),
        ],
        default='military',
    )
    description = models.TextField('配方描述', blank=True)
    safety_level = models.CharField(
        '安全等级',
        max_length=20,
        choices=SAFETY_LEVEL_CHOICES,
        default='medium',
    )
    safety_note = models.TextField('安全说明', blank=True)
    review_status = models.CharField(
        '评审状态',
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
        default='draft',
    )
    archive_status = models.CharField(
        '归档状态',
        max_length=20,
        choices=ARCHIVE_STATUS_CHOICES,
        default='active',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='创建人',
        related_name='created_formulas',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '配方条目'
        verbose_name_plural = '配方条目'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.formula_no} - {self.name}'

    @property
    def total_percentage(self):
        total = self.ingredients.aggregate(total=Sum('percentage'))['total']
        return round(total, 4) if total else 0.0

    def clean(self):
        super().clean()
        errors = {}

        if self.pk:
            total = self.total_percentage
            if self.ingredients.exists() and abs(total - 100.0) > 0.01:
                errors['ingredients'] = f'成分比例合计必须等于 100%，当前为 {total}%'

        if self.review_status == 'pending' and not self.literature:
            errors['literature'] = '缺少文献出处的配方不能提交评审'

        if self.safety_level == 'high' and not self.safety_note.strip():
            errors['safety_note'] = '高风险配方必须填写安全说明'

        if self.archive_status == 'archived' and self.review_status != 'approved':
            errors['archive_status'] = '未完成安全评审的条目不能归档'

        if errors:
            raise ValidationError(errors)


class Ingredient(models.Model):
    formula = models.ForeignKey(
        Formula,
        on_delete=models.CASCADE,
        verbose_name='所属配方',
        related_name='ingredients',
    )
    name = models.CharField('成分名称', max_length=100)
    chinese_name = models.CharField('中文古称', max_length=100, blank=True)
    percentage = models.FloatField('占比 (%)', default=0.0)
    remark = models.CharField('备注', max_length=300, blank=True)

    class Meta:
        verbose_name = '配方成分'
        verbose_name_plural = '配方成分'
        ordering = ['formula', '-percentage']
        unique_together = [['formula', 'name']]

    def __str__(self):
        return f'{self.name}: {self.percentage}%'

    def clean(self):
        super().clean()
        if self.percentage < 0 or self.percentage > 100:
            raise ValidationError({'percentage': '占比必须在 0% 到 100% 之间'})


class SafetyReview(models.Model):
    formula = models.ForeignKey(
        Formula,
        on_delete=models.CASCADE,
        verbose_name='所属配方',
        related_name='reviews',
    )
    reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='评审人',
    )
    review_result = models.CharField(
        '评审结果',
        max_length=20,
        choices=[
            ('approved', '通过'),
            ('rejected', '驳回'),
            ('recheck', '待复核'),
        ],
    )
    opinion = models.TextField('评审意见', blank=True)
    risk_analysis = models.TextField('风险分析', blank=True)
    reviewed_at = models.DateTimeField('评审时间', default=timezone.now)

    class Meta:
        verbose_name = '安全评审'
        verbose_name_plural = '安全评审'
        ordering = ['-reviewed_at']

    def __str__(self):
        return f'{self.formula.formula_no} - {self.get_review_result_display()}'
