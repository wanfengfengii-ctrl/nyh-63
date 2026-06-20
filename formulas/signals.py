from django.db.models.signals import post_save, post_delete
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from .models import (
    Ingredient, Formula, OperationLog, RiskAlert,
    UserProfile, ReviewFlow, Literature,
)


def _get_client_ip(request):
    try:
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0].strip()
            return request.META.get('REMOTE_ADDR')
    except Exception:
        pass
    return None


def log_operation(user, operation_type, target_model='', target_id='',
                  target_name='', description='', old_value='', new_value='',
                  request=None):
    try:
        ip = _get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''
        OperationLog.objects.create(
            user=user if (user and user.is_authenticated) else None,
            operation_type=operation_type,
            target_model=target_model,
            target_id=str(target_id),
            target_name=target_name,
            description=description,
            old_value=str(old_value)[:2000],
            new_value=str(new_value)[:2000],
            ip_address=ip,
            user_agent=ua,
        )
    except Exception:
        pass


def check_and_create_risk_alerts(formula):
    if formula.safety_level == 'high':
        existing = RiskAlert.objects.filter(
            formula=formula,
            alert_type='high_risk_formula',
            status__in=['open', 'acknowledged'],
        ).first()
        if not existing:
            RiskAlert.objects.create(
                formula=formula,
                alert_type='high_risk_formula',
                level='critical' if formula.risk_score >= 70 else 'warning',
                title=f'高风险配方预警：{formula.formula_no}',
                message=f'配方「{formula.name}」被标记为高风险，风险分值 {formula.risk_score}，请及时处理。',
                risk_score=formula.risk_score,
            )
    if formula.safety_level == 'high' and not formula.safety_note.strip():
        existing = RiskAlert.objects.filter(
            formula=formula,
            alert_type='missing_safety_note',
            status__in=['open', 'acknowledged'],
        ).first()
        if not existing:
            RiskAlert.objects.create(
                formula=formula,
                alert_type='missing_safety_note',
                level='warning',
                title=f'缺少安全说明：{formula.formula_no}',
                message=f'高风险配方「{formula.name}」未填写安全说明，请补充。',
                risk_score=formula.risk_score,
            )


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    profile, _ = UserProfile.objects.get_or_create(user=instance)
    if instance.is_superuser and profile.role != 'admin':
        profile.role = 'admin'
        profile.save()


@receiver(user_logged_in)
def on_user_login(sender, request, user, **kwargs):
    log_operation(user, 'login', target_model='User', target_id=user.pk,
                  target_name=user.username, description='用户登录系统', request=request)


@receiver(user_logged_out)
def on_user_logout(sender, request, user, **kwargs):
    if user and user.is_authenticated:
        log_operation(user, 'logout', target_model='User', target_id=user.pk,
                      target_name=user.username, description='用户登出系统', request=request)


@receiver(post_save, sender=Ingredient)
def reset_review_on_ingredient_save(sender, instance, created, **kwargs):
    formula = instance.formula
    old_status = formula.review_status
    if formula.review_status == 'approved':
        Formula.objects.filter(pk=formula.pk).update(review_status='recheck')
        ReviewFlow.objects.create(
            formula=formula,
            step='revision',
            operator=None,
            from_status=old_status,
            to_status='recheck',
            comment=f'成分「{instance.name}」被{"创建" if created else "修改"}，系统自动重置为待复核',
        )
    desc = f'成分「{instance.name}」占比 {instance.percentage}%，{"创建" if created else "更新"}'
    log_operation(None, 'create' if created else 'update',
                  target_model='Ingredient', target_id=instance.pk,
                  target_name=f'{formula.formula_no}/{instance.name}',
                  description=desc)


@receiver(post_delete, sender=Ingredient)
def reset_review_on_ingredient_delete(sender, instance, **kwargs):
    try:
        formula = instance.formula
        old_status = formula.review_status
        if formula.review_status == 'approved':
            Formula.objects.filter(pk=formula.pk).update(review_status='recheck')
            ReviewFlow.objects.create(
                formula=formula,
                step='revision',
                operator=None,
                from_status=old_status,
                to_status='recheck',
                comment=f'成分「{instance.name}」被删除，系统自动重置为待复核',
            )
        log_operation(None, 'delete', target_model='Ingredient', target_id=instance.pk,
                      target_name=f'{formula.formula_no}/{instance.name}',
                      description=f'删除成分「{instance.name}」')
    except Formula.DoesNotExist:
        pass


@receiver(post_save, sender=Formula)
def on_formula_save(sender, instance, created, **kwargs):
    check_and_create_risk_alerts(instance)
    desc = f'配方 {instance.formula_no} - {instance.name}，{"创建" if created else "更新"}'
    log_operation(None, 'create' if created else 'update',
                  target_model='Formula', target_id=instance.pk,
                  target_name=str(instance), description=desc)
    if created and not instance.versions.exists():
        try:
            instance.create_version_snapshot()
        except Exception:
            pass


@receiver(post_delete, sender=Formula)
def on_formula_delete(sender, instance, **kwargs):
    log_operation(None, 'delete', target_model='Formula', target_id=instance.pk,
                  target_name=str(instance),
                  description=f'删除配方 {instance.formula_no} - {instance.name}')


@receiver(post_save, sender=Literature)
def on_literature_save(sender, instance, created, **kwargs):
    log_operation(None, 'create' if created else 'update',
                  target_model='Literature', target_id=instance.pk,
                  target_name=instance.title,
                  description=f'文献「{instance.title}」{"创建" if created else "更新"}')


@receiver(post_delete, sender=Literature)
def on_literature_delete(sender, instance, **kwargs):
    log_operation(None, 'delete', target_model='Literature', target_id=instance.pk,
                  target_name=instance.title,
                  description=f'删除文献「{instance.title}」')


def check_review_overdue():
    try:
        cutoff = timezone.now() - timedelta(days=getattr(settings, 'REVIEW_OVERDUE_DAYS', 7))
        overdue = Formula.objects.filter(
            review_status__in=['pending', 'recheck'],
            updated_at__lt=cutoff,
        )
        for f in overdue:
            existing = RiskAlert.objects.filter(
                formula=f,
                alert_type='review_overdue',
                status__in=['open', 'acknowledged'],
            ).first()
            if not existing:
                RiskAlert.objects.create(
                    formula=f,
                    alert_type='review_overdue',
                    level='warning',
                    title=f'评审超期：{f.formula_no}',
                    message=f'配方「{f.name}」当前状态为{f.get_review_status_display()}，已超过{settings.REVIEW_OVERDUE_DAYS}天未处理。',
                    risk_score=f.risk_score,
                )
    except Exception:
        pass
