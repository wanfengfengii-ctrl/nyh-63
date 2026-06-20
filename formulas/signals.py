from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Ingredient, Formula


@receiver(post_save, sender=Ingredient)
def reset_review_on_ingredient_save(sender, instance, **kwargs):
    formula = instance.formula
    if formula.review_status == 'approved':
        Formula.objects.filter(pk=formula.pk).update(review_status='recheck')


@receiver(post_delete, sender=Ingredient)
def reset_review_on_ingredient_delete(sender, instance, **kwargs):
    formula = instance.formula
    if formula.review_status == 'approved':
        Formula.objects.filter(pk=formula.pk).update(review_status='recheck')
