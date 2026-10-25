from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def home(request):
    from integrations.views import active_snapshot
    from integrations.jobs import module_settings
    return render(request, 'home.html', {'mode': 'home', 'crm_mode': True, 'snapshot':active_snapshot(request.user), 'options':module_settings()})
