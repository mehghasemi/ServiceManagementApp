from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

@login_required
def home(request):
    if request.session.get("dashboard_view") == "today":
        return redirect("planning-today")
    from integrations.views import active_snapshot
    from integrations.jobs import module_settings
    from config.access import member
    from planning.charts import status_distribution, creation_chart
    from integrations.views import current_cases
    from django.utils import timezone
    overview={}
    if member(request.user):
        cases=current_cases(request.user)
        overview={'case_count':cases.count(), 'status_chart':status_distribution(cases), 'creation':creation_chart(cases,timezone.localdate())}
    return render(request, 'home.html', {**overview,'mode': 'home', 'crm_mode': True, 'snapshot':active_snapshot(request.user), 'options':module_settings()})
