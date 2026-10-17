from django.conf import settings
from django.db.models import Q


def shared_queryset(queryset, user, field='owner'):
    """LAN members share this company workspace; source/View scoping stays mandatory."""
    if settings.SERVICE_LAN:
        return queryset
    return queryset.filter(**{field: user})


def open_actions_filter(user):
    result = Q(local_actions__status='open')
    return result if settings.SERVICE_LAN else result & Q(local_actions__actor=user)


def member(user):
    return user.is_authenticated and user.is_active and not (settings.SERVICE_LAN and user.username == 'local-preview') and (user.is_staff or user.groups.filter(name='service-readers').exists())
