from django.urls import path
from . import views

app_name = 'formulas'

urlpatterns = [
    path('', views.index, name='index'),

    path('formulas/', views.formula_list, name='formula_list'),
    path('formulas/<int:pk>/', views.formula_detail, name='formula_detail'),
    path('formulas/create/', views.formula_create, name='formula_create'),
    path('formulas/<int:pk>/edit/', views.formula_edit, name='formula_edit'),
    path('formulas/<int:pk>/submit-review/', views.formula_submit_review, name='formula_submit_review'),
    path('formulas/<int:pk>/toggle-archive/', views.formula_toggle_archive, name='formula_toggle_archive'),

    path('literatures/', views.literature_list, name='literature_list'),
    path('literatures/<int:pk>/', views.literature_detail, name='literature_detail'),
    path('literatures/create/', views.literature_create, name='literature_create'),
    path('attachments/<int:pk>/delete/', views.literature_attachment_delete, name='attachment_delete'),

    path('compare/', views.formula_compare, name='formula_compare'),
    path('search/', views.advanced_search, name='advanced_search'),
    path('statistics/', views.statistics, name='statistics'),
    path('export/', views.data_export, name='data_export'),
    path('logs/', views.operation_logs, name='operation_logs'),
    path('alerts/', views.risk_alerts, name='risk_alerts'),
    path('profile/', views.user_profile, name='user_profile'),

    path('annotations/', views.annotation_list, name='annotation_list'),
    path('annotations/<int:pk>/', views.annotation_detail, name='annotation_detail'),
    path('annotations/create/', views.annotation_create, name='annotation_create'),
    path('annotations/<int:pk>/edit/', views.annotation_edit, name='annotation_edit'),
    path('annotations/<int:pk>/delete/', views.annotation_delete, name='annotation_delete'),

    path('disputes/', views.dispute_list, name='dispute_list'),
    path('disputes/<int:pk>/', views.dispute_detail, name='dispute_detail'),
    path('disputes/create/', views.dispute_create, name='dispute_create'),
    path('disputes/<int:pk>/delete/', views.dispute_delete, name='dispute_delete'),

    path('topics/', views.topic_list, name='topic_list'),
    path('topics/<int:pk>/', views.topic_detail, name='topic_detail'),
    path('topics/create/', views.topic_create, name='topic_create'),
    path('topics/<int:pk>/edit/', views.topic_edit, name='topic_edit'),
    path('topics/<int:pk>/delete/', views.topic_delete, name='topic_delete'),
    path('topics/<int:pk>/export/', views.topic_export, name='topic_export'),
]
