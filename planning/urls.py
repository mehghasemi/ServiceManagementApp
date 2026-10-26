"""Public entry points owned by the planning subsystem."""
from django.urls import path
from criteria import views as criteria_views
from integrations import views
from . import upgrade_views, backlogs

urlpatterns = [
    path('visits/periodic/records/<uuid:identifier>/', backlogs.detail, {'module': 'periodic'}, name='periodic-detail'),
    path('visits/periodic/settings/', backlogs.settings_page, {'module': 'periodic'}, name='periodic-settings'),
    path('visits/periodic/jobs/<str:kind>/', backlogs.begin, {'module': 'periodic'}, name='periodic-start'),
    path('visits/onsite/', upgrade_views.onsite, name='planning-onsite'),
    path('visits/periodic/', backlogs.visits, {'kind': 'periodic'}, name='planning-periodic'),
    path('backlogs/criteria/', criteria_views.settings, {'module': 'backlogs'}, name='backlogs-criteria'),
    path('backlogs/criteria/new/', criteria_views.edit, {'module': 'backlogs'}, name='backlogs-rule-new'),
    path('backlogs/criteria/<int:pk>/', criteria_views.edit, {'module': 'backlogs'}, name='backlogs-rule-edit'),
    path('backlogs/', backlogs.dashboard, name='backlogs'),
    path('backlogs/settings/', backlogs.settings_page, name='backlogs-settings'),
    path('backlogs/jobs/<str:kind>/', backlogs.begin, name='backlogs-start'),
    path('backlogs/<uuid:identifier>/', backlogs.detail, name='backlog-detail'),
    path('upgrades/', upgrade_views.dashboard, name='planning-upgrades'),
    path('cases/<int:identifier>/refresh/', views.refresh_record, {'module': 'planning'}, name='case-refresh'),
    path('attention/', criteria_views.attention, {'module': 'planning'}, name='planning-attention'),
    path('criteria/', criteria_views.settings, {'module': 'planning'}, name='planning-criteria'),
    path('criteria/new/', criteria_views.edit, {'module': 'planning'}, name='planning-rule-new'),
    path('criteria/<int:pk>/', criteria_views.edit, {'module': 'planning'}, name='planning-rule-edit'),
    path('suggestions/', views.suggestions_page, name='planning-suggestions'),
    path('', views.dashboard, name='planning-dashboard'),
    path('cases/<int:pk>/', views.case_detail, name='crm-case'),
    path('cases/<int:pk>/actions/new/', views.create_action, name='crm-action-new'),
    path('actions/', views.actions_page, name='crm-actions'),
    path('actions/<int:pk>/complete/', views.complete_action, name='crm-action-complete'),
]
