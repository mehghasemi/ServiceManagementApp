from django.urls import path
from criteria import views as criteria_views
from . import views
from integrations.views import settings_page, refresh_record

urlpatterns = [
    path('<uuid:identifier>/refresh/', refresh_record, {'module': 'projects'}, name='project-refresh'),
    path('attention/', criteria_views.attention, {'module': 'projects'}, name='projects-attention'),
    path('criteria/', criteria_views.settings, {'module': 'projects'}, name='projects-criteria'),
    path('criteria/new/', criteria_views.edit, {'module': 'projects'}, name='projects-rule-new'),
    path('criteria/<int:pk>/', criteria_views.edit, {'module': 'projects'}, name='projects-rule-edit'),
    path('', views.dashboard, name='projects-dashboard'),
    path('settings/', settings_page, {'module': 'projects'}, name='projects-settings'),
    path('jobs/<str:kind>/', views.begin_job, name='projects-start-job'),
    path('<uuid:identifier>/', views.detail, name='project-detail'),
]
