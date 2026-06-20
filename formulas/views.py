from collections import defaultdict
from functools import wraps
import csv
import json
from io import StringIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import models
from django.db.models import Count, Avg, Q, Sum, F
from django.http import (
    HttpResponse, HttpResponseForbidden, HttpResponseBadRequest,
)
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    Formula, Literature, Ingredient, SafetyReview,
    UserProfile, OperationLog, FormulaVersion,
    LiteratureAttachment, RiskAlert, ReviewFlow,
)
from .forms import (
    FormulaForm, IngredientFormSet, LiteratureForm,
    SafetyReviewForm, FormulaFilterForm,
    LiteratureAttachmentForm, AdvancedSearchForm,
    FormulaCompareForm, UserProfileForm, AlertHandleForm,
    OperationLogFilterForm, DataExportForm, LiteratureFilterForm,
)
from .signals import log_operation, check_review_overdue


ROLE_LABELS = {
    'admin': '系统管理员',
    'curator': '文献馆员',
    'researcher': '研究员',
    'reviewer': '安全评审员',
    'auditor': '审计员',
    'guest': '访客',
}


def get_user_role(user):
    if not user or not user.is_authenticated:
        return 'guest'
    profile = get_user_profile(user)
    return profile.role


def get_user_profile(user):
    if not user or not user.is_authenticated:
        return None
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if user.is_superuser and profile.role != 'admin':
        profile.role = 'admin'
        profile.save()
    return profile


def has_perm(user, perm):
    if not user or not user.is_authenticated:
        return perm == 'view'
    profile = get_user_profile(user)
    return profile.has_permission(perm)


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            user_role = get_user_role(request.user)
            if user_role in roles or user_role == 'admin':
                return view_func(request, *args, **kwargs)
            raise PermissionDenied('您没有执行此操作的权限')
        return _wrapped_view
    return decorator


def perm_required(perm):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if has_perm(request.user, perm):
                return view_func(request, *args, **kwargs)
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            raise PermissionDenied('您没有执行此操作的权限')
        return _wrapped_view
    return decorator


def index(request):
    check_review_overdue()
    total_formulas = Formula.objects.count()
    total_literatures = Literature.objects.count()
    total_attachments = LiteratureAttachment.objects.count()
    pending_reviews = Formula.objects.filter(review_status='pending').count()
    recheck_count = Formula.objects.filter(review_status='recheck').count()
    archived = Formula.objects.filter(archive_status='archived').count()
    high_risk = Formula.objects.filter(safety_level='high').count()
    open_alerts = RiskAlert.objects.filter(status='open')
    critical_alerts = open_alerts.filter(level='critical').count()
    warning_alerts = open_alerts.filter(level='warning').count()
    my_pending = 0
    if request.user.is_authenticated:
        user_role = get_user_role(request.user)
        if user_role in ['reviewer', 'admin']:
            my_pending = pending_reviews + recheck_count
        elif user_role in ['researcher', 'curator']:
            my_pending = Formula.objects.filter(
                created_by=request.user, review_status__in=['draft', 'recheck']
            ).count()

    recent_formulas = Formula.objects.select_related(
        'literature', 'created_by'
    ).order_by('-created_at')[:5]
    recent_alerts = RiskAlert.objects.select_related('formula').order_by('-created_at')[:5]
    recent_logs = OperationLog.objects.select_related('user').order_by('-created_at')[:8]

    usage_stats = list(Formula.objects.values('usage_category').annotate(
        count=Count('id')
    ).order_by('-count'))
    safety_stats = list(Formula.objects.values('safety_level').annotate(
        count=Count('id')
    ))
    review_stats = list(Formula.objects.values('review_status').annotate(
        count=Count('id')
    ))
    user_role = get_user_role(request.user) if request.user.is_authenticated else 'guest'

    context = {
        'total_formulas': total_formulas,
        'total_literatures': total_literatures,
        'total_attachments': total_attachments,
        'pending_reviews': pending_reviews,
        'recheck_count': recheck_count,
        'archived': archived,
        'high_risk': high_risk,
        'open_alerts_count': open_alerts.count(),
        'critical_alerts': critical_alerts,
        'warning_alerts': warning_alerts,
        'my_pending': my_pending,
        'recent_formulas': recent_formulas,
        'recent_alerts': recent_alerts,
        'recent_logs': recent_logs,
        'usage_stats': usage_stats,
        'safety_stats': safety_stats,
        'review_stats': review_stats,
        'user_role': user_role,
        'user_role_label': ROLE_LABELS.get(user_role, '访客'),
    }
    return render(request, 'formulas/index.html', context)


def formula_list(request):
    form = FormulaFilterForm(request.GET or None)
    queryset = Formula.objects.select_related(
        'literature', 'created_by'
    ).all().order_by('-created_at')

    if form.is_valid():
        era = form.cleaned_data.get('era')
        region = form.cleaned_data.get('region')
        usage_category = form.cleaned_data.get('usage_category')
        safety_level = form.cleaned_data.get('safety_level')
        review_status = form.cleaned_data.get('review_status')
        archive_status = form.cleaned_data.get('archive_status')
        keyword = form.cleaned_data.get('keyword')

        if era:
            queryset = queryset.filter(
                Q(era__icontains=era)
                | Q(literature__dynasty__icontains=era)
            )
        if region:
            queryset = queryset.filter(region__icontains=region)
        if usage_category:
            queryset = queryset.filter(usage_category=usage_category)
        if safety_level:
            queryset = queryset.filter(safety_level=safety_level)
        if review_status:
            queryset = queryset.filter(review_status=review_status)
        if archive_status:
            queryset = queryset.filter(archive_status=archive_status)
        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(formula_no__icontains=keyword)
                | Q(alias__icontains=keyword)
            )

    log_operation(request.user, 'view', target_model='Formula',
                  target_name='配方列表', description='浏览配方列表', request=request)

    context = {
        'form': form,
        'formulas': queryset,
        'user_role': get_user_role(request.user) if request.user.is_authenticated else 'guest',
    }
    return render(request, 'formulas/formula_list.html', context)


def formula_detail(request, pk):
    formula = get_object_or_404(Formula, pk=pk)
    ingredients = formula.ingredients.all().order_by('-percentage')
    reviews = formula.reviews.all().select_related('reviewer').order_by('-reviewed_at')
    versions = formula.versions.all().order_by('-version')
    review_flows = formula.review_flows.all().select_related('operator').order_by('created_at')
    risk_alerts = formula.risk_alerts.all().order_by('-created_at')

    log_operation(request.user, 'view', target_model='Formula', target_id=formula.pk,
                  target_name=str(formula), description=f'查看配方详情：{formula}',
                  request=request)

    review_form = SafetyReviewForm(request.POST or None)
    user_role = get_user_role(request.user) if request.user.is_authenticated else 'guest'
    can_review = has_perm(request.user, 'review')

    if request.method == 'POST' and can_review and review_form.is_valid():
        old_status = formula.review_status
        review = review_form.save(commit=False)
        review.formula = formula
        review.reviewer = request.user
        review.save()

        if review.review_result == 'approved':
            formula.review_status = 'approved'
            step = 'final_approval'
        elif review.review_result == 'rejected':
            formula.review_status = 'rejected'
            step = 'rejection'
        else:
            formula.review_status = 'recheck'
            step = 'secondary_review'
        formula.save()

        ReviewFlow.objects.create(
            formula=formula,
            step=step,
            operator=request.user,
            from_status=old_status,
            to_status=formula.review_status,
            comment=review.opinion[:500],
        )

        log_operation(request.user, 'review', target_model='Formula', target_id=formula.pk,
                      target_name=str(formula),
                      description=f'评审配方：结果={review.get_review_result_display()}',
                      request=request)

        messages.success(request, '评审意见已提交')
        return redirect('formulas:formula_detail', pk=pk)

    context = {
        'formula': formula,
        'ingredients': ingredients,
        'reviews': reviews,
        'review_form': review_form,
        'versions': versions,
        'review_flows': review_flows,
        'risk_alerts': risk_alerts,
        'can_review': can_review,
        'user_role': user_role,
    }
    return render(request, 'formulas/formula_detail.html', context)


@login_required
@perm_required('create')
def formula_create(request):
    if request.method == 'POST':
        form = FormulaForm(request.POST)
        formset = IngredientFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            formula = form.save(commit=False)
            formula.created_by = request.user
            formula.updated_by = request.user
            change_note = form.cleaned_data.get('change_note', '')

            temp_ingredients = []
            for ing_form in formset:
                if ing_form.cleaned_data and not ing_form.cleaned_data.get('DELETE', False):
                    ing = ing_form.save(commit=False)
                    temp_ingredients.append(ing)

            total = sum(ing.percentage for ing in temp_ingredients) if temp_ingredients else 0
            if temp_ingredients and abs(total - 100.0) > 0.01:
                form.add_error(None, f'成分比例合计必须等于 100%，当前合计为 {round(total, 2)}%')
            else:
                formula.save()
                formset.instance = formula

                ingredients = formset.save(commit=False)
                for ing in ingredients:
                    ing.formula = formula
                    ing.save()

                for obj in formset.deleted_objects:
                    obj.delete()

                try:
                    formula.full_clean()
                except ValidationError as e:
                    for field, errors in e.message_dict.items():
                        for err in errors:
                            messages.warning(request, f'{field}: {err}')

                formula.create_version_snapshot(request.user)
                if change_note:
                    v = formula.versions.latest('created_at')
                    v.change_note = change_note
                    v.save()

                log_operation(request.user, 'create', target_model='Formula',
                              target_id=formula.pk, target_name=str(formula),
                              description=f'创建配方：{formula}', request=request)

                messages.success(request, '配方已创建')
                return redirect('formulas:formula_detail', pk=formula.pk)
    else:
        form = FormulaForm()
        formset = IngredientFormSet()

    context = {
        'form': form,
        'formset': formset,
        'title': '新建配方',
    }
    return render(request, 'formulas/formula_form.html', context)


@login_required
@perm_required('update')
def formula_edit(request, pk):
    formula = get_object_or_404(Formula, pk=pk)
    old_status = formula.review_status

    if request.method == 'POST':
        form = FormulaForm(request.POST, instance=formula)
        formset = IngredientFormSet(request.POST, instance=formula)

        if form.is_valid() and formset.is_valid():
            change_note = form.cleaned_data.get('change_note', '')
            temp_ingredients = []
            for ing_form in formset:
                if ing_form.cleaned_data and not ing_form.cleaned_data.get('DELETE', False):
                    if ing_form.instance and ing_form.instance.pk:
                        ing = ing_form.save(commit=False)
                        temp_ingredients.append(ing)
                    else:
                        ing = ing_form.save(commit=False)
                        temp_ingredients.append(ing)

            total = sum(ing.percentage for ing in temp_ingredients) if temp_ingredients else 0
            if temp_ingredients and abs(total - 100.0) > 0.01:
                form.add_error(None, f'成分比例合计必须等于 100%，当前合计为 {round(total, 2)}%')
            else:
                formula = form.save(commit=False)
                formula.updated_by = request.user
                if old_status != formula.review_status and formula.review_status == 'pending':
                    ReviewFlow.objects.create(
                        formula=formula,
                        step='submit',
                        operator=request.user,
                        from_status=old_status,
                        to_status=formula.review_status,
                        comment=change_note[:500],
                    )
                    log_operation(request.user, 'submit', target_model='Formula',
                                  target_id=formula.pk, target_name=str(formula),
                                  description='提交评审', request=request)
                formula.save()
                formset.save()

                formula.version += 1
                formula.save()
                formula.create_version_snapshot(request.user)
                if change_note:
                    v = formula.versions.latest('created_at')
                    v.change_note = change_note
                    v.save()

                try:
                    formula.full_clean()
                except ValidationError as e:
                    for field, errors in e.message_dict.items():
                        for err in errors:
                            messages.warning(request, f'{field}: {err}')

                log_operation(request.user, 'update', target_model='Formula',
                              target_id=formula.pk, target_name=str(formula),
                              description=f'编辑配方：{formula}', request=request)

                messages.success(request, '配方已更新')
                return redirect('formulas:formula_detail', pk=formula.pk)
    else:
        form = FormulaForm(instance=formula)
        formset = IngredientFormSet(instance=formula)

    context = {
        'form': form,
        'formset': formset,
        'title': '编辑配方',
        'formula': formula,
    }
    return render(request, 'formulas/formula_form.html', context)


@login_required
@perm_required('update')
def formula_submit_review(request, pk):
    formula = get_object_or_404(Formula, pk=pk)
    if formula.review_status in ['draft', 'rejected', 'recheck']:
        errors = []
        if not formula.literature:
            errors.append('请先关联文献出处后再提交评审')
        if formula.safety_level == 'high' and not formula.safety_note.strip():
            errors.append('高风险配方必须填写安全说明后才能提交评审')
        if errors:
            for err in errors:
                messages.error(request, err)
            return redirect('formulas:formula_detail', pk=pk)
        old_status = formula.review_status
        formula.review_status = 'pending'
        try:
            formula.full_clean()
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                for err in errors:
                    messages.error(request, err)
            formula.review_status = old_status
            return redirect('formulas:formula_detail', pk=pk)
        formula.save()
        ReviewFlow.objects.create(
            formula=formula,
            step='submit',
            operator=request.user,
            from_status=old_status,
            to_status='pending',
        )
        log_operation(request.user, 'submit', target_model='Formula',
                      target_id=formula.pk, target_name=str(formula),
                      description='提交评审', request=request)
        messages.success(request, '配方已提交评审')
    else:
        messages.warning(request, '当前状态不能提交评审')
    return redirect('formulas:formula_detail', pk=pk)


@login_required
@perm_required('update')
def formula_toggle_archive(request, pk):
    formula = get_object_or_404(Formula, pk=pk)
    if formula.archive_status == 'active':
        if formula.review_status != 'approved':
            messages.error(request, '未完成安全评审的配方不能归档')
            return redirect('formulas:formula_detail', pk=pk)
        formula.archive_status = 'archived'
        op = 'archive'
    else:
        formula.archive_status = 'active'
        op = 'unarchive'
    formula.save()
    log_operation(request.user, op, target_model='Formula',
                  target_id=formula.pk, target_name=str(formula),
                  description=f'{"归档" if op == "archive" else "解档"}配方',
                  request=request)
    messages.success(request, f'配方已{"归档" if op == "archive" else "解档"}')
    return redirect('formulas:formula_detail', pk=pk)


def literature_list(request):
    form = LiteratureFilterForm(request.GET or None)
    queryset = Literature.objects.prefetch_related('attachments').all().order_by('-publication_year')
    if form.is_valid():
        keyword = form.cleaned_data.get('keyword')
        source_type = form.cleaned_data.get('source_type')
        dynasty = form.cleaned_data.get('dynasty')
        author = form.cleaned_data.get('author')
        if keyword:
            queryset = queryset.filter(
                Q(title__icontains=keyword)
                | Q(author__icontains=keyword)
                | Q(call_number__icontains=keyword)
            )
        if source_type:
            queryset = queryset.filter(source_type=source_type)
        if dynasty:
            queryset = queryset.filter(dynasty__icontains=dynasty)
        if author:
            queryset = queryset.filter(author__icontains=author)
    context = {'literatures': queryset, 'form': form}
    return render(request, 'formulas/literature_list.html', context)


def literature_detail(request, pk):
    literature = get_object_or_404(Literature, pk=pk)
    formulas = literature.formulas.all()
    attachments = literature.attachments.all()
    attachment_form = None
    if has_perm(request.user, 'upload'):
        attachment_form = LiteratureAttachmentForm(request.POST or None, request.FILES or None)
        if request.method == 'POST' and attachment_form.is_valid():
            att = attachment_form.save(commit=False)
            att.literature = literature
            att.uploaded_by = request.user
            att.save()
            log_operation(request.user, 'upload', target_model='LiteratureAttachment',
                          target_id=att.pk, target_name=att.file_name,
                          description=f'上传附件到文献：{literature.title}',
                          request=request)
            messages.success(request, '附件已上传')
            return redirect('formulas:literature_detail', pk=pk)
    log_operation(request.user, 'view', target_model='Literature',
                  target_id=literature.pk, target_name=literature.title,
                  description=f'查看文献详情：{literature.title}', request=request)
    context = {
        'literature': literature,
        'formulas': formulas,
        'attachments': attachments,
        'attachment_form': attachment_form,
        'can_upload': has_perm(request.user, 'upload'),
    }
    return render(request, 'formulas/literature_detail.html', context)


@login_required
@perm_required('upload')
def literature_attachment_delete(request, pk):
    att = get_object_or_404(LiteratureAttachment, pk=pk)
    lit_pk = att.literature.pk
    log_operation(request.user, 'delete', target_model='LiteratureAttachment',
                  target_id=att.pk, target_name=att.file_name,
                  description=f'删除附件：{att.file_name}', request=request)
    att.delete()
    messages.success(request, '附件已删除')
    return redirect('formulas:literature_detail', pk=lit_pk)


@login_required
@perm_required('create')
def literature_create(request):
    if request.method == 'POST':
        form = LiteratureForm(request.POST)
        if form.is_valid():
            literature = form.save(commit=False)
            literature.created_by = request.user
            literature.save()
            log_operation(request.user, 'create', target_model='Literature',
                          target_id=literature.pk, target_name=literature.title,
                          description=f'创建文献：{literature.title}', request=request)
            messages.success(request, '文献已添加')
            return redirect('formulas:literature_detail', pk=literature.pk)
    else:
        form = LiteratureForm()
    return render(request, 'formulas/literature_form.html', {'form': form, 'title': '添加文献'})


def formula_compare(request):
    form = FormulaCompareForm(request.GET or None)
    comparison = None
    if form.is_valid() and form.cleaned_data.get('formula_a') and form.cleaned_data.get('formula_b'):
        fa = form.cleaned_data['formula_a']
        fb = form.cleaned_data['formula_b']
        va = form.cleaned_data.get('version_a')
        vb = form.cleaned_data.get('version_b')
        data_a = _get_formula_version_data(fa, va)
        data_b = _get_formula_version_data(fb, vb)
        comparison = {
            'a': data_a,
            'b': data_b,
            'common_ingredients': [],
            'only_a': [],
            'only_b': [],
        }
        names_a = {i['name'] for i in data_a['ingredients']}
        names_b = {i['name'] for i in data_b['ingredients']}
        ing_map_a = {i['name']: i for i in data_a['ingredients']}
        ing_map_b = {i['name']: i for i in data_b['ingredients']}
        for name in sorted(names_a & names_b):
            comparison['common_ingredients'].append({
                'name': name,
                'pct_a': ing_map_a[name]['percentage'],
                'pct_b': ing_map_b[name]['percentage'],
                'diff': round(ing_map_a[name]['percentage'] - ing_map_b[name]['percentage'], 4),
            })
        for name in sorted(names_a - names_b):
            comparison['only_a'].append(ing_map_a[name])
        for name in sorted(names_b - names_a):
            comparison['only_b'].append(ing_map_b[name])
    log_operation(request.user, 'view', target_model='FormulaCompare',
                  target_name='配方对比', description='进行配方对比', request=request)
    context = {'form': form, 'comparison': comparison}
    return render(request, 'formulas/formula_compare.html', context)


def _get_formula_version_data(formula, version_num=None):
    if version_num:
        v = get_object_or_404(FormulaVersion, formula=formula, version=version_num)
        return {
            'formula': formula,
            'version': v,
            'version_num': v.version,
            'name': v.name,
            'alias': v.alias,
            'description': v.description,
            'safety_level': v.safety_level,
            'safety_note': v.safety_note,
            'ingredients': v.ingredients_list,
            'created_at': v.created_at,
            'created_by': v.created_by,
            'change_note': v.change_note,
        }
    ings = [{
        'name': i.name,
        'chinese_name': i.chinese_name,
        'percentage': i.percentage,
        'remark': i.remark,
    } for i in formula.ingredients.all().order_by('-percentage')]
    return {
        'formula': formula,
        'version': None,
        'version_num': formula.version,
        'name': formula.name,
        'alias': formula.alias,
        'description': formula.description,
        'safety_level': formula.safety_level,
        'safety_note': formula.safety_note,
        'ingredients': ings,
        'created_at': formula.updated_at,
        'created_by': formula.updated_by,
        'change_note': '',
    }


def advanced_search(request):
    form = AdvancedSearchForm(request.GET or None)
    results = Formula.objects.select_related('literature').none()
    executed = False
    if form.is_valid():
        cd = form.cleaned_data
        mode = cd.get('search_mode', 'and')
        qs = Formula.objects.select_related('literature').all()
        queries = []
        if cd.get('formula_no'):
            queries.append(Q(formula_no__icontains=cd['formula_no']))
        if cd.get('name'):
            queries.append(Q(name__icontains=cd['name']))
        if cd.get('alias'):
            queries.append(Q(alias__icontains=cd['alias']))
        if cd.get('ingredient_name'):
            ing_q = Ingredient.objects.filter(name__icontains=cd['ingredient_name'])
            pmin = cd.get('ingredient_percentage_min')
            pmax = cd.get('ingredient_percentage_max')
            if pmin is not None:
                ing_q = ing_q.filter(percentage__gte=pmin)
            if pmax is not None:
                ing_q = ing_q.filter(percentage__lte=pmax)
            formula_ids = ing_q.values_list('formula_id', flat=True)
            queries.append(Q(pk__in=formula_ids))
        if cd.get('literature_title'):
            queries.append(Q(literature__title__icontains=cd['literature_title']))
        if cd.get('author'):
            queries.append(Q(literature__author__icontains=cd['author']))
        if cd.get('dynasty'):
            queries.append(
                Q(dynasty__icontains=cd['dynasty'])
                | Q(literature__dynasty__icontains=cd['dynasty'])
            )
        pmin = cd.get('publication_year_min')
        pmax = cd.get('publication_year_max')
        if pmin is not None or pmax is not None:
            yq = Q()
            if pmin is not None:
                yq &= (Q(era_year__gte=pmin) | Q(literature__publication_year__gte=pmin))
            if pmax is not None:
                yq &= (Q(era_year__lte=pmax) | Q(literature__publication_year__lte=pmax))
            queries.append(yq)
        if cd.get('region'):
            queries.append(Q(region__icontains=cd['region']))
        if cd.get('usage_category'):
            queries.append(Q(usage_category=cd['usage_category']))
        if cd.get('safety_level'):
            queries.append(Q(safety_level=cd['safety_level']))
        if cd.get('review_status'):
            queries.append(Q(review_status=cd['review_status']))
        if cd.get('created_by'):
            queries.append(Q(created_by__username__icontains=cd['created_by']))
        if queries:
            if mode == 'or':
                combined = queries[0]
                for q in queries[1:]:
                    combined |= q
                qs = qs.filter(combined)
            else:
                for q in queries:
                    qs = qs.filter(q)
        results = qs.distinct().order_by('-created_at')
        executed = True
    log_operation(request.user, 'view', target_model='AdvancedSearch',
                  target_name='高级检索', description='使用高级检索', request=request)
    context = {
        'form': form,
        'results': results,
        'executed': executed,
    }
    return render(request, 'formulas/advanced_search.html', context)


@login_required
@perm_required('view_logs')
def operation_logs(request):
    form = OperationLogFilterForm(request.GET or None)
    queryset = OperationLog.objects.select_related('user').all()
    if form.is_valid():
        cd = form.cleaned_data
        if cd.get('user'):
            queryset = queryset.filter(user__username__icontains=cd['user'])
        if cd.get('operation_type'):
            queryset = queryset.filter(operation_type=cd['operation_type'])
        if cd.get('target_model'):
            queryset = queryset.filter(target_model__icontains=cd['target_model'])
        if cd.get('target_name'):
            queryset = queryset.filter(target_name__icontains=cd['target_name'])
        if cd.get('date_from'):
            queryset = queryset.filter(created_at__date__gte=cd['date_from'])
        if cd.get('date_to'):
            queryset = queryset.filter(created_at__date__lte=cd['date_to'])
    queryset = queryset.order_by('-created_at')[:500]
    context = {'form': form, 'logs': queryset}
    return render(request, 'formulas/operation_logs.html', context)


def risk_alerts(request):
    alerts = RiskAlert.objects.select_related('formula', 'handled_by').all().order_by('-created_at')
    status_filter = request.GET.get('status', '')
    level_filter = request.GET.get('level', '')
    if status_filter:
        alerts = alerts.filter(status=status_filter)
    if level_filter:
        alerts = alerts.filter(level=level_filter)
    handle_form = None
    if has_perm(request.user, 'update'):
        handle_form = AlertHandleForm()
        if request.method == 'POST':
            alert_id = request.POST.get('alert_id')
            alert = get_object_or_404(RiskAlert, pk=alert_id)
            handle_form = AlertHandleForm(request.POST, instance=alert)
            if handle_form.is_valid():
                a = handle_form.save(commit=False)
                a.handled_by = request.user
                if a.status in ['resolved', 'dismissed', 'acknowledged']:
                    a.handled_at = timezone.now()
                a.save()
                log_operation(request.user, 'update', target_model='RiskAlert',
                              target_id=a.pk, target_name=a.title,
                              description=f'处理预警：{a.title}', request=request)
                messages.success(request, '预警状态已更新')
                return redirect('formulas:risk_alerts')
    context = {
        'alerts': alerts,
        'status_filter': status_filter,
        'level_filter': level_filter,
        'handle_form': handle_form,
        'can_handle': has_perm(request.user, 'update'),
    }
    return render(request, 'formulas/risk_alerts.html', context)


def statistics(request):
    formulas = Formula.objects.all()
    total_count = formulas.count()

    usage_stats = formulas.values('usage_category').annotate(
        count=Count('id')
    ).order_by('-count')

    safety_stats = formulas.values('safety_level').annotate(
        count=Count('id')
    ).order_by('-count')

    review_stats = formulas.values('review_status').annotate(
        count=Count('id')
    )

    archive_stats = formulas.values('archive_status').annotate(
        count=Count('id')
    )

    ingredient_stats = Ingredient.objects.values('name').annotate(
        count=Count('id'),
        avg_percentage=Avg('percentage'),
    ).order_by('-count')[:20]

    region_stats = formulas.exclude(region='').values('region').annotate(
        count=Count('id')
    ).order_by('-count')[:15]

    dynasty_stats = formulas.exclude(era='').values('era').annotate(
        count=Count('id')
    ).order_by('-count')[:15]

    role_stats = UserProfile.objects.values('role').annotate(count=Count('id'))

    ingredient_distribution = defaultdict(list)
    for ing in Ingredient.objects.select_related('formula').all():
        ingredient_distribution[ing.name].append({
            'formula_no': ing.formula.formula_no,
            'formula_name': ing.formula.name,
            'percentage': ing.percentage,
        })

    alert_stats = RiskAlert.objects.values('level', 'status').annotate(count=Count('id'))

    context = {
        'total_count': total_count,
        'usage_stats': usage_stats,
        'safety_stats': safety_stats,
        'review_stats': review_stats,
        'archive_stats': archive_stats,
        'ingredient_stats': ingredient_stats,
        'region_stats': region_stats,
        'dynasty_stats': dynasty_stats,
        'role_stats': role_stats,
        'ingredient_distribution': dict(ingredient_distribution),
        'alert_stats': alert_stats,
    }
    return render(request, 'formulas/statistics.html', context)


@login_required
@perm_required('export')
def data_export(request):
    form = DataExportForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        target = cd['export_target']
        fmt = cd['export_format']
        date_from = cd.get('date_from')
        date_to = cd.get('date_to')
        include_attachments = cd.get('include_attachments', False)

        if target == 'operation_logs':
            if not has_perm(request.user, 'view_logs'):
                raise PermissionDenied('您没有导出操作日志的权限')

        log_operation(request.user, 'export', target_model=target,
                      target_name=f'导出{target}', description=f'导出{target}数据',
                      request=request)

        data, filename = _build_export_data(
            target, fmt, date_from, date_to, include_attachments
        )

        if fmt == 'csv':
            response = HttpResponse(data, content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
            response.write('\ufeff')
            response.write(data)
            return response
        else:
            response = HttpResponse(data, content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="{filename}.json"'
            return response

    context = {
        'form': form,
        'can_export_logs': has_perm(request.user, 'view_logs'),
    }
    return render(request, 'formulas/data_export.html', context)


def _build_export_data(target, fmt, date_from, date_to, include_attachments):
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    q_filter = Q()
    if date_from:
        q_filter &= Q(created_at__date__gte=date_from)
    if date_to:
        q_filter &= Q(created_at__date__lte=date_to)

    if target == 'formulas':
        rows = []
        formulas = Formula.objects.filter(q_filter).select_related(
            'literature', 'created_by'
        ).prefetch_related('ingredients')
        for f in formulas:
            ingredients = '; '.join(
                f"{i.name}({i.chinese_name}):{i.percentage}%"
                for i in f.ingredients.all()
            )
            rows.append({
                '配方编号': f.formula_no,
                '配方名称': f.name,
                '别名': f.alias,
                '文献出处': str(f.literature) if f.literature else '',
                '文献页码': f.literature_page,
                '年代': f.era,
                '具体年份': f.era_year or '',
                '来源地区': f.region,
                '用途分类': f.get_usage_category_display(),
                '安全等级': f.get_safety_level_display(),
                '安全说明': f.safety_note,
                '评审状态': f.get_review_status_display(),
                '归档状态': f.get_archive_status_display(),
                '版本号': f.version,
                '成分列表': ingredients,
                '描述': f.description,
                '创建人': str(f.created_by) if f.created_by else '',
                '创建时间': f.created_at.strftime('%Y-%m-%d %H:%M'),
            })
        if fmt == 'csv':
            return _rows_to_csv(rows), f'formulas_{timestamp}'
        return json.dumps(rows, ensure_ascii=False, indent=2), f'formulas_{timestamp}'

    elif target == 'formulas_basic':
        rows = []
        formulas = Formula.objects.filter(q_filter).select_related('literature', 'created_by')
        for f in formulas:
            rows.append({
                '配方编号': f.formula_no,
                '配方名称': f.name,
                '别名': f.alias,
                '文献出处': str(f.literature) if f.literature else '',
                '年代': f.era,
                '具体年份': f.era_year or '',
                '来源地区': f.region,
                '用途分类': f.get_usage_category_display(),
                '安全等级': f.get_safety_level_display(),
                '评审状态': f.get_review_status_display(),
                '创建人': str(f.created_by) if f.created_by else '',
                '创建时间': f.created_at.strftime('%Y-%m-%d %H:%M'),
            })
        if fmt == 'csv':
            return _rows_to_csv(rows), f'formulas_basic_{timestamp}'
        return json.dumps(rows, ensure_ascii=False, indent=2), f'formulas_basic_{timestamp}'

    elif target == 'literatures':
        rows = []
        lits = Literature.objects.filter(q_filter).prefetch_related('attachments')
        for lit in lits:
            r = {
                '文献标题': lit.title,
                '作者': lit.author,
                '出版年代': lit.publication_year or '',
                '朝代': lit.dynasty,
                '来源地区': lit.region,
                '出版机构': lit.publisher,
                '索书号': lit.call_number,
                '文献类型': lit.get_source_type_display(),
                '备注': lit.remark,
                '录入人': str(lit.created_by) if lit.created_by else '',
                '创建时间': lit.created_at.strftime('%Y-%m-%d %H:%M'),
            }
            if include_attachments:
                atts = '; '.join(a.file_name for a in lit.attachments.all())
                r['附件列表'] = atts
            rows.append(r)
        if fmt == 'csv':
            return _rows_to_csv(rows), f'literatures_{timestamp}'
        return json.dumps(rows, ensure_ascii=False, indent=2), f'literatures_{timestamp}'

    elif target == 'ingredients':
        rows = []
        ings = Ingredient.objects.filter(q_filter).select_related('formula')
        for i in ings:
            rows.append({
                '配方编号': i.formula.formula_no,
                '配方名称': i.formula.name,
                '成分名称': i.name,
                '中文古称': i.chinese_name,
                '占比(%)': i.percentage,
                '备注': i.remark,
            })
        if fmt == 'csv':
            return _rows_to_csv(rows), f'ingredients_{timestamp}'
        return json.dumps(rows, ensure_ascii=False, indent=2), f'ingredients_{timestamp}'

    elif target == 'reviews':
        rows = []
        reviews = SafetyReview.objects.filter(q_filter).select_related('formula', 'reviewer')
        for r in reviews:
            rows.append({
                '配方编号': r.formula.formula_no,
                '配方名称': r.formula.name,
                '评审人': str(r.reviewer) if r.reviewer else '',
                '评审结果': r.get_review_result_display(),
                '评审意见': r.opinion,
                '风险分析': r.risk_analysis,
                '评审时间': r.reviewed_at.strftime('%Y-%m-%d %H:%M'),
            })
        if fmt == 'csv':
            return _rows_to_csv(rows), f'reviews_{timestamp}'
        return json.dumps(rows, ensure_ascii=False, indent=2), f'reviews_{timestamp}'

    elif target == 'operation_logs':
        rows = []
        logs = OperationLog.objects.filter(q_filter).select_related('user')[:5000]
        for log in logs:
            rows.append({
                '操作时间': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                '操作用户': str(log.user) if log.user else '',
                '操作类型': log.get_operation_type_display(),
                '对象类型': log.target_model,
                '对象名称': log.target_name,
                '操作描述': log.description,
                'IP地址': log.ip_address or '',
            })
        if fmt == 'csv':
            return _rows_to_csv(rows), f'operation_logs_{timestamp}'
        return json.dumps(rows, ensure_ascii=False, indent=2), f'operation_logs_{timestamp}'

    return '', f'export_{timestamp}'


def _rows_to_csv(rows):
    if not rows:
        return ''
    buf = StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


@login_required
def user_profile(request):
    profile = get_user_profile(request.user)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            log_operation(request.user, 'update', target_model='UserProfile',
                          target_id=profile.pk, target_name=request.user.username,
                          description='更新个人资料', request=request)
            messages.success(request, '个人资料已更新')
            return redirect('formulas:user_profile')
    else:
        form = UserProfileForm(instance=profile)
    context = {
        'form': form,
        'profile': profile,
        'role_label': ROLE_LABELS.get(profile.role, '访客'),
    }
    return render(request, 'formulas/user_profile.html', context)
