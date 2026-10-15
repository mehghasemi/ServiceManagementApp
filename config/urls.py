from django.urls import path, include
from django.contrib.staticfiles.views import serve
from planning import views
from integrations import views as crm
from config.views import home

urlpatterns = [
    path('', home, name='home'),
    path('projects/', include('projects.urls')),
    path('planning/', include('planning.urls')),
    path('settings/', crm.settings_page, name='system-settings'),
    path('settings/planning/', crm.settings_page, {'module': True}, name='planning-settings'),
    path('crm/jobs/start/<str:kind>/', crm.begin_job, name='crm-start-job'),
    path('crm/jobs/<int:pk>/', crm.job_status, name='crm-job'),
    path('crm/jobs/<int:pk>/cancel/', crm.cancel_job, name='crm-cancel-job'),
    path('demo/today/', views.board, name='today'),
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
