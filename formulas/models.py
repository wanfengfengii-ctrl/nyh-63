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


ANNOTATION_TYPE_CHOICES = [
    ('term', '术语释义'),
    ('version_diff', '版本差异'),
    ('synonym', '成分名称异名'),
    ('authenticity', '出处真伪'),
    ('usage', '用途判断'),
    ('safety', '安全解读'),
]

DISPUTE_TYPE_CHOICES = [
    ('authenticity', '文献真伪争议'),
    ('ingredient', '成分辨识争议'),
    ('proportion', '比例换算争议'),
    ('dating', '年代断代争议'),
    ('usage', '用途判断争议'),
    ('safety', '安全解读争议'),
    ('other', '其他争议'),
]

DISPUTE_STATUS_CHOICES = [
    ('open', '讨论中'),
    ('evidence', '证据收集中'),
    ('review', '专家评审中'),
    ('resolved', '已达成共识'),
    ('unresolved', '暂无定论'),
    ('withdrawn', '已撤回'),
]


class AcademicAnnotation(models.Model):
    content_type = models.CharField(
        '注释对象类型',
        max_length=20,
        choices=[
            ('formula', '配方'),
            ('literature', '文献'),
        ],
    )
    formula = models.ForeignKey(
        Formula,
        on_delete=models.CASCADE,
        verbose_name='关联配方',
        related_name='annotations',
        null=True,
        blank=True,
    )
    literature = models.ForeignKey(
        Literature,
        on_delete=models.CASCADE,
        verbose_name='关联文献',
        related_name='annotations',
        null=True,
        blank=True,
    )
    annotation_type = models.CharField(
        '注释类型',
        max_length=20,
        choices=ANNOTATION_TYPE_CHOICES,
    )
    title = models.CharField('注释标题', max_length=300)
    content = models.TextField('注释内容')
    reference = models.TextField('依据文献', blank=True)
    reference_page = models.CharField('依据文献页码/章节', max_length=100, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='注释人',
        related_name='created_annotations',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '学术注释'
        verbose_name_plural = '学术注释'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'annotation_type']),
            models.Index(fields=['formula', 'created_at']),
            models.Index(fields=['literature', 'created_at']),
        ]

    def __str__(self):
        return f'[{self.get_annotation_type_display()}] {self.title}'

    def clean(self):
        super().clean()
        if self.content_type == 'formula' and not self.formula:
            raise ValidationError({'formula': '配方类型注释必须关联配方'})
        if self.content_type == 'literature' and not self.literature:
            raise ValidationError({'literature': '文献类型注释必须关联文献'})
        if not self.formula and not self.literature:
            raise ValidationError('注释必须关联配方或文献')


class AnnotationEditHistory(models.Model):
    annotation = models.ForeignKey(
        AcademicAnnotation,
        on_delete=models.CASCADE,
        verbose_name='所属注释',
        related_name='edit_history',
    )
    old_content = models.TextField('修改前内容')
    new_content = models.TextField('修改后内容')
    edit_reason = models.CharField('修改原因', max_length=500, blank=True)
    edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='修改人',
    )
    edited_at = models.DateTimeField('修改时间', auto_now_add=True)

    class Meta:
        verbose_name = '注释修改历史'
        verbose_name_plural = '注释修改历史'
        ordering = ['-edited_at']

    def __str__(self):
        return f'{self.annotation.title} - 修改于 {self.edited_at.strftime("%Y-%m-%d %H:%M")}'


class Dispute(models.Model):
    formula = models.ForeignKey(
        Formula,
        on_delete=models.CASCADE,
        verbose_name='关联配方',
        related_name='disputes',
        null=True,
        blank=True,
    )
    literature = models.ForeignKey(
        Literature,
        on_delete=models.CASCADE,
        verbose_name='关联文献',
        related_name='disputes',
        null=True,
        blank=True,
    )
    dispute_type = models.CharField(
        '争议类型',
        max_length=30,
        choices=DISPUTE_TYPE_CHOICES,
    )
    title = models.CharField('争议标题', max_length=300)
    description = models.TextField('争议描述')
    status = models.CharField(
        '处理状态',
        max_length=20,
        choices=DISPUTE_STATUS_CHOICES,
        default='open',
    )
    conclusion = models.TextField('结论', blank=True)
    initiated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='发起人',
        related_name='initiated_disputes',
    )
    initiated_at = models.DateTimeField('发起时间', auto_now_add=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='解决人',
        related_name='resolved_disputes',
    )
    resolved_at = models.DateTimeField('解决时间', null=True, blank=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '争议条目'
        verbose_name_plural = '争议条目'
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['dispute_type', 'status']),
            models.Index(fields=['formula', 'initiated_at']),
            models.Index(fields=['literature', 'initiated_at']),
        ]

    def __str__(self):
        return f'[{self.get_dispute_type_display()}] {self.title}'


class DisputeArgument(models.Model):
    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        verbose_name='所属争议',
        related_name='arguments',
    )
    stance = models.CharField(
        '立场',
        max_length=20,
        choices=[
            ('support', '支持'),
            ('oppose', '反对'),
            ('neutral', '中立'),
        ],
    )
    viewpoint = models.TextField('观点内容')
    evidence = models.TextField('证据材料', blank=True)
    evidence_reference = models.CharField('证据出处', max_length=500, blank=True)
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='提交人',
    )
    submitted_at = models.DateTimeField('提交时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '争议观点'
        verbose_name_plural = '争议观点'
        ordering = ['submitted_at']

    def __str__(self):
        return f'{self.dispute.title} - {self.get_stance_display()} - {self.submitted_by}'


class DisputeProgress(models.Model):
    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        verbose_name='所属争议',
        related_name='progress_records',
    )
    old_status = models.CharField(
        '原状态',
        max_length=20,
        choices=DISPUTE_STATUS_CHOICES,
        blank=True,
    )
    new_status = models.CharField(
        '新状态',
        max_length=20,
        choices=DISPUTE_STATUS_CHOICES,
    )
    comment = models.TextField('处理说明', blank=True)
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='操作人',
    )
    operated_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '争议处理记录'
        verbose_name_plural = '争议处理记录'
        ordering = ['operated_at']

    def __str__(self):
        return f'{self.dispute.title} - {self.get_new_status_display()}'


TOPIC_CATEGORY_CHOICES = [
    ('dynasty', '特定朝代'),
    ('region', '地区'),
    ('ingredient', '成分'),
    ('usage', '用途'),
    ('literature_system', '文献体系'),
    ('other', '其他'),
]

TOPIC_STATUS_CHOICES = [
    ('planning', '规划中'),
    ('in_progress', '研究中'),
    ('completed', '已完成'),
    ('published', '已发布'),
]

TOPIC_ENTRY_TYPE_CHOICES = [
    ('formula', '配方'),
    ('literature', '文献'),
    ('annotation', '注释'),
    ('dispute', '争议'),
    ('review', '评审'),
]

TOPIC_NOTE_TYPE_CHOICES = [
    ('research_note', '研究说明'),
    ('conclusion', '阶段结论'),
    ('finding', '研究发现'),
    ('question', '待解问题'),
]


class ResearchTopic(models.Model):
    title = models.CharField('专题名称', max_length=300)
    description = models.TextField('专题描述', blank=True)
    category = models.CharField(
        '主题类别',
        max_length=30,
        choices=TOPIC_CATEGORY_CHOICES,
        default='other',
    )
    status = models.CharField(
        '研究状态',
        max_length=20,
        choices=TOPIC_STATUS_CHOICES,
        default='planning',
    )
    leader = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='专题负责人',
        related_name='led_topics',
    )
    research_note = models.TextField('研究说明', blank=True)
    stage_conclusion = models.TextField('阶段结论', blank=True)
    started_at = models.DateField('研究开始日期', null=True, blank=True)
    completed_at = models.DateField('研究完成日期', null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='创建人',
        related_name='created_topics',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '研究专题'
        verbose_name_plural = '研究专题'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['leader', 'status']),
        ]

    def __str__(self):
        return f'[{self.get_category_display()}] {self.title}'

    @property
    def entry_count(self):
        return self.entries.count()

    @property
    def formula_count(self):
        return self.entries.filter(content_type='formula').count()

    @property
    def literature_count(self):
        return self.entries.filter(content_type='literature').count()

    @property
    def annotation_count(self):
        return self.entries.filter(content_type='annotation').count()

    @property
    def dispute_count(self):
        return self.entries.filter(content_type='dispute').count()

    @property
    def review_count(self):
        return self.entries.filter(content_type='review').count()


class TopicKeyword(models.Model):
    topic = models.ForeignKey(
        ResearchTopic,
        on_delete=models.CASCADE,
        verbose_name='所属专题',
        related_name='keywords',
    )
    keyword = models.CharField('关键词', max_length=100)

    class Meta:
        verbose_name = '专题关键词'
        verbose_name_plural = '专题关键词'
        unique_together = [['topic', 'keyword']]

    def __str__(self):
        return f'{self.topic.title} - {self.keyword}'


class TopicReference(models.Model):
    topic = models.ForeignKey(
        ResearchTopic,
        on_delete=models.CASCADE,
        verbose_name='所属专题',
        related_name='references',
    )
    title = models.CharField('参考资料标题', max_length=300)
    author = models.CharField('作者', max_length=200, blank=True)
    source = models.CharField('来源', max_length=300, blank=True)
    url = models.URLField('链接', blank=True)
    note = models.TextField('备注', blank=True)
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='添加人',
    )
    added_at = models.DateTimeField('添加时间', auto_now_add=True)

    class Meta:
        verbose_name = '专题参考资料'
        verbose_name_plural = '专题参考资料'
        ordering = ['-added_at']

    def __str__(self):
        return f'{self.topic.title} - {self.title}'


class TopicEntry(models.Model):
    topic = models.ForeignKey(
        ResearchTopic,
        on_delete=models.CASCADE,
        verbose_name='所属专题',
        related_name='entries',
    )
    content_type = models.CharField(
        '条目类型',
        max_length=20,
        choices=TOPIC_ENTRY_TYPE_CHOICES,
    )
    formula = models.ForeignKey(
        Formula,
        on_delete=models.CASCADE,
        verbose_name='关联配方',
        related_name='topic_entries',
        null=True,
        blank=True,
    )
    literature = models.ForeignKey(
        Literature,
        on_delete=models.CASCADE,
        verbose_name='关联文献',
        related_name='topic_entries',
        null=True,
        blank=True,
    )
    annotation = models.ForeignKey(
        AcademicAnnotation,
        on_delete=models.CASCADE,
        verbose_name='关联注释',
        related_name='topic_entries',
        null=True,
        blank=True,
    )
    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        verbose_name='关联争议',
        related_name='topic_entries',
        null=True,
        blank=True,
    )
    review = models.ForeignKey(
        SafetyReview,
        on_delete=models.CASCADE,
        verbose_name='关联评审',
        related_name='topic_entries',
        null=True,
        blank=True,
    )
    note = models.TextField('归集说明', blank=True)
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='添加人',
    )
    added_at = models.DateTimeField('添加时间', auto_now_add=True)

    class Meta:
        verbose_name = '专题条目'
        verbose_name_plural = '专题条目'
        ordering = ['-added_at']
        indexes = [
            models.Index(fields=['topic', 'content_type']),
        ]

    def __str__(self):
        obj_name = ''
        if self.content_type == 'formula' and self.formula:
            obj_name = str(self.formula)
        elif self.content_type == 'literature' and self.literature:
            obj_name = self.literature.title
        elif self.content_type == 'annotation' and self.annotation:
            obj_name = self.annotation.title
        elif self.content_type == 'dispute' and self.dispute:
            obj_name = self.dispute.title
        elif self.content_type == 'review' and self.review:
            obj_name = str(self.review)
        return f'{self.topic.title} - {self.get_content_type_display()}: {obj_name}'

    def clean(self):
        super().clean()
        ct_field_map = {
            'formula': self.formula,
            'literature': self.literature,
            'annotation': self.annotation,
            'dispute': self.dispute,
            'review': self.review,
        }
        selected = ct_field_map.get(self.content_type)
        if not selected:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {self.content_type: f'{self.get_content_type_display()}类型条目必须关联对应对象'}
            )


class TopicNote(models.Model):
    topic = models.ForeignKey(
        ResearchTopic,
        on_delete=models.CASCADE,
        verbose_name='所属专题',
        related_name='notes',
    )
    note_type = models.CharField(
        '笔记类型',
        max_length=20,
        choices=TOPIC_NOTE_TYPE_CHOICES,
        default='research_note',
    )
    title = models.CharField('标题', max_length=300)
    content = models.TextField('内容')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='创建人',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '专题笔记'
        verbose_name_plural = '专题笔记'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.topic.title} - {self.title}'


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
