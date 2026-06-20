from collections import defaultdict
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Avg
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden
from .models import Formula, Literature, Ingredient, SafetyReview
from .forms import (
    FormulaForm,
    IngredientFormSet,
    LiteratureForm,
    SafetyReviewForm,
    FormulaFilterForm,
)


def index(request):
    total_formulas = Formula.objects.count()
    total_literatures = Literature.objects.count()
    pending_reviews = Formula.objects.filter(review_status='pending').count()
    archived = Formula.objects.filter(archive_status='archived').count()
    high_risk = Formula.objects.filter(safety_level='high').count()
    recent_formulas = Formula.objects.select_related('literature').order_by('-created_at')[:5]

    context = {
        'total_formulas': total_formulas,
        'total_literatures': total_literatures,
        'pending_reviews': pending_reviews,
        'archived': archived,
        'high_risk': high_risk,
        'recent_formulas': recent_formulas,
    }
    return render(request, 'formulas/index.html', context)


def formula_list(request):
    form = FormulaFilterForm(request.GET or None)
    queryset = Formula.objects.select_related('literature').all().order_by('-created_at')

    if form.is_valid():
        era = form.cleaned_data.get('era')
        region = form.cleaned_data.get('region')
        usage_category = form.cleaned_data.get('usage_category')
        safety_level = form.cleaned_data.get('safety_level')
        review_status = form.cleaned_data.get('review_status')
        keyword = form.cleaned_data.get('keyword')

        if era:
            queryset = queryset.filter(era__icontains=era)
        if region:
            queryset = queryset.filter(region__icontains=region)
        if usage_category:
            queryset = queryset.filter(usage_category=usage_category)
        if safety_level:
            queryset = queryset.filter(safety_level=safety_level)
        if review_status:
            queryset = queryset.filter(review_status=review_status)
        if keyword:
            queryset = queryset.filter(
                models.Q(name__icontains=keyword)
                | models.Q(formula_no__icontains=keyword)
                | models.Q(alias__icontains=keyword)
            )

    context = {
        'form': form,
        'formulas': queryset,
    }
    return render(request, 'formulas/formula_list.html', context)


def formula_detail(request, pk):
    formula = get_object_or_404(Formula, pk=pk)
    ingredients = formula.ingredients.all().order_by('-percentage')
    reviews = formula.reviews.all().order_by('-reviewed_at')

    review_form = SafetyReviewForm(request.POST or None)
    if request.method == 'POST' and review_form.is_valid():
        if not request.user.is_authenticated:
            return HttpResponseForbidden()
        review = review_form.save(commit=False)
        review.formula = formula
        review.reviewer = request.user
        review.save()

        if review.review_result == 'approved':
            formula.review_status = 'approved'
        elif review.review_result == 'rejected':
            formula.review_status = 'rejected'
        else:
            formula.review_status = 'recheck'
        formula.save()

        messages.success(request, '评审意见已提交')
        return redirect('formulas:formula_detail', pk=pk)

    context = {
        'formula': formula,
        'ingredients': ingredients,
        'reviews': reviews,
        'review_form': review_form,
    }
    return render(request, 'formulas/formula_detail.html', context)


@login_required
def formula_create(request):
    if request.method == 'POST':
        form = FormulaForm(request.POST)
        formset = IngredientFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            formula = form.save(commit=False)
            formula.created_by = request.user

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
def formula_edit(request, pk):
    formula = get_object_or_404(Formula, pk=pk)

    if request.method == 'POST':
        form = FormulaForm(request.POST, instance=formula)
        formset = IngredientFormSet(request.POST, instance=formula)

        if form.is_valid() and formset.is_valid():
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
                formula = form.save()
                formset.save()

                try:
                    formula.full_clean()
                except ValidationError as e:
                    for field, errors in e.message_dict.items():
                        for err in errors:
                            messages.warning(request, f'{field}: {err}')

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


def literature_list(request):
    literatures = Literature.objects.all().order_by('-publication_year')
    return render(request, 'formulas/literature_list.html', {'literatures': literatures})


def literature_detail(request, pk):
    literature = get_object_or_404(Literature, pk=pk)
    formulas = literature.formulas.all()
    return render(request, 'formulas/literature_detail.html', {
        'literature': literature,
        'formulas': formulas,
    })


@login_required
def literature_create(request):
    if request.method == 'POST':
        form = LiteratureForm(request.POST)
        if form.is_valid():
            literature = form.save()
            messages.success(request, '文献已添加')
            return redirect('formulas:literature_detail', pk=literature.pk)
    else:
        form = LiteratureForm()
    return render(request, 'formulas/literature_form.html', {'form': form, 'title': '添加文献'})


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

    ingredient_stats = Ingredient.objects.values('name').annotate(
        count=Count('id'),
        avg_percentage=Avg('percentage'),
    ).order_by('-count')[:15]

    region_stats = formulas.exclude(region='').values('region').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    ingredient_distribution = defaultdict(list)
    for ing in Ingredient.objects.select_related('formula').all():
        ingredient_distribution[ing.name].append({
            'formula_no': ing.formula.formula_no,
            'formula_name': ing.formula.name,
            'percentage': ing.percentage,
        })

    context = {
        'total_count': total_count,
        'usage_stats': usage_stats,
        'safety_stats': safety_stats,
        'review_stats': review_stats,
        'ingredient_stats': ingredient_stats,
        'region_stats': region_stats,
        'ingredient_distribution': dict(ingredient_distribution),
    }
    return render(request, 'formulas/statistics.html', context)
