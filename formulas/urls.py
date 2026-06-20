from django.urls import path
from . import views

app_name = 'formulas'

urlpatterns = [
    path('', views.index, name='index'),
    path('formulas/', views.formula_list, name='formula_list'),
    path('formulas/<int:pk>/', views.formula_detail, name='formula_detail'),
    path('formulas/create/', views.formula_create, name='formula_create'),
    path('formulas/<int:pk>/edit/', views.formula_edit, name='formula_edit'),
    path('literatures/', views.literature_list, name='literature_list'),
    path('literatures/<int:pk>/', views.literature_detail, name='literature_detail'),
    path('literatures/create/', views.literature_create, name='literature_create'),
    path('statistics/', views.statistics, name='statistics'),
]
