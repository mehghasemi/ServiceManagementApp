"""Public entry points owned by the planning subsystem."""
from django.urls import path
from integrations import views

urlpatterns = [
    path('suggestions/', views.suggestions_page, name='planning-suggestions'),
    path('', views.dashboard, name='planning-dashboard'),
    path('cases/<int:pk>/', views.case_detail, name='crm-case'),
    path('cases/<int:pk>/actions/new/', views.create_action, name='crm-action-new'),
    path('actions/', views.actions_page, name='crm-actions'),
    path('actions/<int:pk>/complete/', views.complete_action, name='crm-action-complete'),
]
