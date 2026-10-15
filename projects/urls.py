from django.urls import path
from . import views
from integrations.views import settings_page

urlpatterns = [
    path('', views.dashboard, name='projects-dashboard'),
    path('settings/', settings_page, {'module': 'projects'}, name='projects-settings'),
    path('jobs/<str:kind>/', views.begin_job, name='projects-start-job'),
    path('<uuid:identifier>/', views.detail, name='project-detail'),
]
