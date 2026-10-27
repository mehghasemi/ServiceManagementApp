from django.urls import path, include
from django.contrib.staticfiles.views import serve
from planning import views
from integrations import views as crm
from config.views import home
from django.conf import settings
from django.views.generic import RedirectView
from config.accounts import users, edit_user, change_password
from config.grid_preferences import preferences

from config.backups import backups
from planning import dashboard_views

urlpatterns = [
    path('dashboards/shared/<slug:key>/',dashboard_views.shared_dashboard,name='shared-dashboard'),
    path('preferences/dashboards/<slug:key>/publish/',dashboard_views.publish,name='dashboard-publish'),
    path('dashboards/',dashboard_views.index,name='personal-dashboards'),
    path('dashboards/<slug:key>/',dashboard_views.dashboard,name='personal-dashboard'),
    path('preferences/dashboards/<slug:key>/',dashboard_views.layout,name='dashboard-layout'),
    path('settings/backups/', backups, name='settings-backups'),
    path('account/password/', change_password, name='change-password'),
    path('network-users/<int:pk>/', edit_user, name='edit-user'),
    path('preferences/grids/<slug:key>/', preferences, name='grid-preferences'),
    path('network-users/', users, name='network-users'),
    path('', home, name='home'),
    path('projects/', include('projects.urls')),
    path('planning/', include('planning.urls')),
    path('settings/', crm.settings_page, name='system-settings'),
    path('settings/planning/', crm.settings_page, {'module': True}, name='planning-settings'),
    path('crm/jobs/start/<str:kind>/', crm.begin_job, name='crm-start-job'),
    path('crm/jobs/<int:pk>/', crm.job_status, name='crm-job'),
    path('crm/jobs/<int:pk>/cancel/', crm.cancel_job, name='crm-cancel-job'),
    path('demo/today/', RedirectView.as_view(pattern_name='planning-dashboard', permanent=False) if settings.SERVICE_ENVIRONMENT == 'stable' else views.board, name='today'),
    path('programs/', views.board, {'mode': 'programs'}, name='programs'),
    path('decisions/', views.board, {'mode': 'decisions'}, name='decisions'),
    path('welcome/', views.welcome, name='welcome'),
    path('logout/', views.sign_out, name='logout'),
    path('programs/new/', views.edit, name='new'),
    path('programs/<int:pk>/', views.detail, name='detail'),
    path('programs/<int:pk>/edit/', views.edit, name='edit'),
    path('programs/<int:pk>/followup/', views.followup, name='followup'),
    path('versions/', views.versions, name='versions'),
    # Local preview assets only; production will use collected static files.
    path('static/<path:path>', serve, {'insecure': True}),
]
handler400 = views.bad_request
handler403 = views.forbidden
handler404 = views.not_found
handler500 = views.server_error
