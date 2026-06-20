from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
import json


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

ROLE_CHOICES = [
    ('admin', '系统管理员'),
    ('curator', '文献馆员'),
    ('researcher', '研究员'),
    ('reviewer', '安全评审员'),
    ('auditor', '审计员'),
    ('guest', '访客'),
]

OPERATION_TYPE_CHOICES = [
    ('create', '创建'),
    ('update', '更新'),
    ('delete', '删除'),
    ('review', '评审'),
    ('submit', '提交'),
    ('archive', '归档'),
    ('unarchive', '解档'),
    ('download', '下载'),
    ('upload', '上传'),
    ('login', '登录'),
    ('logout', '登出'),
    ('export', '导出'),
    ('view', '查看'),
]

ALERT_LEVEL_CHOICES = [
    ('info', '提示'),
    ('warning', '警告'),
    ('critical', '严重'),
]

ALERT_STATUS_CHOICES = [
    ('open', '未处理'),
    ('acknowledged', '已确认'),
    ('resolved', '已解决'),
    ('dismissed', '已忽略'),
]

REVIEW_STEP_CHOICES = [
    ('submit', '提交评审'),
    ('primary_review', '初审'),
    ('secondary_review', '复核'),
    ('final_approval', '终审'),
    ('rejection', '驳回'),
    ('revision', '修改待审'),
]


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        verbose_name='关联用户',
        related_name='profile',
    )
    role = models.CharField(
        '角色',
        max_length=20,
        choices=ROLE_CHOICES,
        default='guest',
    )
    department = models.CharField('所属部门/团队', max_length=200, blank=True)
    phone = models.CharField('联系电话', max_length=50, blank=True)
    bio = models.TextField('个人简介', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '用户角色档案'
        verbose_name_plural = '用户角色档案'

    def __str__(self):
        return f'{self.user.username} - {self.get_role_display()}'

    @property
    def role_permissions(self):
        perm_map = {
            'admin': ['all'],
            'curator': ['view', 'create', 'update', 'upload', 'export'],
            'researcher': ['view', 'create', 'update', 'export'],
            'reviewer': ['view', 'review', 'export'],
            'auditor': ['view', 'export', 'view_logs'],
            'guest': ['view'],
        }
        return perm_map.get(self.role, ['view'])

    def has_permission(self, perm):
        if 'all' in self.role_permissions:
            return True
        return perm in self.role_permissions


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
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='录入人',
        related_name='created_literatures',
    )
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


class LiteratureAttachment(models.Model):
    literature = models.ForeignKey(
        Literature,
        on_delete=models.CASCADE,
        verbose_name='所属文献',
        related_name='attachments',
    )
    file = models.FileField(
        '附件文件',
        upload_to='literature_attachments/%Y/%m/',
    )
    file_name = models.CharField('文件显示名称', max_length=300, blank=True)
    file_type = models.CharField(
        '文件类型',
        max_length=50,
        choices=[
            ('pdf', 'PDF文档'),
            ('image', '图片'),
            ('doc', 'Word文档'),
            ('other', '其他'),
        ],
        default='other',
    )
    description = models.CharField('文件说明', max_length=500, blank=True)
    page_reference = models.CharField('对应页码/章节', max_length=100, blank=True)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='上传人',
    )
    uploaded_at = models.DateTimeField('上传时间', auto_now_add=True)

    class Meta:
        verbose_name = '文献附件'
        verbose_name_plural = '文献附件'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.literature.title} - {self.file_name or self.file.name}'

    def save(self, *args, **kwargs):
        if not self.file_name and self.file:
            self.file_name = self.file.name.split('/')[-1]
        super().save(*args, **kwargs)


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
    version = models.PositiveIntegerField('当前版本号', default=1)
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
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='最后修改人',
        related_name='updated_formulas',
    )

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

    @property
    def risk_score(self):
        score = 0
        if self.safety_level == 'high':
            score += 50
        elif self.safety_level == 'medium':
            score += 25
        high_risk_ings = ['硝石', '硝酸钾', '硫磺', '雄黄', '雌黄']
        for ing in self.ingredients.all():
            for hri in high_risk_ings:
                if hri in ing.name or hri in ing.chinese_name:
                    score += 20
                    break
        if self.usage_category == 'military':
            score += 20
        return min(score, 100)

    def create_version_snapshot(self, user=None):
        ingredients_data = []
        for ing in self.ingredients.all():
            ingredients_data.append({
                'name': ing.name,
                'chinese_name': ing.chinese_name,
                'percentage': ing.percentage,
                'remark': ing.remark,
            })
        FormulaVersion.objects.create(
            formula=self,
            version=self.version,
            name=self.name,
            alias=self.alias,
            description=self.description,
            safety_level=self.safety_level,
            safety_note=self.safety_note,
            ingredients_json=json.dumps(ingredients_data, ensure_ascii=False),
            created_by=user,
        )

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


class FormulaVersion(models.Model):
    formula = models.ForeignKey(
        Formula,
        on_delete=models.CASCADE,
        verbose_name='所属配方',
        related_name='versions',
    )
    version = models.PositiveIntegerField('版本号')
    name = models.CharField('配方名称', max_length=200)
    alias = models.CharField('别名', max_length=200, blank=True)
    description = models.TextField('配方描述', blank=True)
    safety_level = models.CharField(
        '安全等级',
        max_length=20,
        choices=SAFETY_LEVEL_CHOICES,
        default='medium',
    )
    safety_note = models.TextField('安全说明', blank=True)
    ingredients_json = models.TextField('成分数据(JSON)')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='创建人',
    )
    created_at = models.DateTimeField('快照时间', auto_now_add=True)
    change_note = models.CharField('版本变更说明', max_length=500, blank=True)

    class Meta:
        verbose_name = '配方版本'
        verbose_name_plural = '配方版本'
        ordering = ['formula', '-version']
        unique_together = [['formula', 'version']]

    def __str__(self):
        return f'{self.formula.formula_no} v{self.version}'

    @property
    def ingredients_list(self):
        try:
            return json.loads(self.ingredients_json)
        except (json.JSONDecodeError, TypeError):
            return []


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


class ReviewFlow(models.Model):
    formula = models.ForeignKey(
        Formula,
        on_delete=models.CASCADE,
        verbose_name='所属配方',
        related_name='review_flows',
    )
    step = models.CharField(
        '流程节点',
        max_length=30,
        choices=REVIEW_STEP_CHOICES,
    )
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='操作人',
    )
    from_status = models.CharField(
        '原状态',
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
        blank=True,
    )
    to_status = models.CharField(
        '目标状态',
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
    )
    comment = models.TextField('备注说明', blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '评审流程记录'
        verbose_name_plural = '评审流程记录'
        ordering = ['formula', 'created_at']

    def __str__(self):
        return f'{self.formula.formula_no} - {self.get_step_display()}'


class OperationLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='操作用户',
    )
    operation_type = models.CharField(
        '操作类型',
        max_length=20,
        choices=OPERATION_TYPE_CHOICES,
    )
    target_model = models.CharField('对象类型', max_length=50, blank=True)
    target_id = models.CharField('对象ID', max_length=100, blank=True)
    target_name = models.CharField('对象名称', max_length=300, blank=True)
    description = models.TextField('操作描述', blank=True)
    old_value = models.TextField('变更前数据', blank=True)
    new_value = models.TextField('变更后数据', blank=True)
    ip_address = models.GenericIPAddressField('IP地址', null=True, blank=True)
    user_agent = models.CharField('浏览器信息', max_length=500, blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '操作日志'
        verbose_name_plural = '操作日志'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['operation_type', 'created_at']),
            models.Index(fields=['target_model', 'target_id']),
        ]

    def __str__(self):
        return f'[{self.created_at}] {self.user} {self.get_operation_type_display()} {self.target_name}'


class RiskAlert(models.Model):
    formula = models.ForeignKey(
        Formula,
        on_delete=models.CASCADE,
        verbose_name='关联配方',
        related_name='risk_alerts',
        null=True,
        blank=True,
    )
    alert_type = models.CharField(
        '预警类型',
        max_length=50,
        choices=[
            ('high_risk_formula', '高风险配方'),
            ('missing_safety_note', '缺少安全说明'),
            ('review_overdue', '评审超期'),
            ('unapproved_access', '未授权访问尝试'),
            ('data_anomaly', '数据异常'),
            ('ingredient_conflict', '成分冲突'),
            ('other', '其他'),
        ],
        default='other',
    )
    level = models.CharField(
        '预警等级',
        max_length=20,
        choices=ALERT_LEVEL_CHOICES,
        default='warning',
    )
    status = models.CharField(
        '处理状态',
        max_length=20,
        choices=ALERT_STATUS_CHOICES,
        default='open',
    )
    title = models.CharField('预警标题', max_length=300)
    message = models.TextField('预警详情', blank=True)
    risk_score = models.PositiveIntegerField('风险分值', default=0)
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_alerts',
        verbose_name='触发用户',
    )
    handled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_alerts',
        verbose_name='处理人',
    )
    handled_at = models.DateTimeField('处理时间', null=True, blank=True)
    handle_note = models.TextField('处理备注', blank=True)
    created_at = models.DateTimeField('触发时间', auto_now_add=True)

    class Meta:
        verbose_name = '风险预警'
        verbose_name_plural = '风险预警'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_level_display()}] {self.title}'

    def mark_handled(self, user, note=''):
        self.status = 'resolved'
        self.handled_by = user
        self.handled_at = timezone.now()
        self.handle_note = note
        self.save()
