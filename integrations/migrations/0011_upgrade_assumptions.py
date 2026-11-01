from django.db import migrations

READY = {'code': 'upgrade-ready', 'label': 'قابل رفع با ارتقا؛ فرض مدیریتی Done', 'dashboard': 'upgrade', 'purpose': 'upgrade_ready', 'metric': 'source_status', 'operator': 'in', 'value': ['Done'], 'active_only': True, 'priority': 1, 'impact': 'فرض مدیریتی: کیس منطبق با اجرای ارتقا قابل رفع است؛ انجام ارتقا و بسته\u200cشدن واقعی جداگانه پیگیری می\u200cشود.'}
PROGRAM = {'code': 'upgrade-program', 'label': 'برنامه نصب نگارش جدید', 'dashboard': 'upgrade', 'purpose': 'upgrade_program', 'metric': 'case_service', 'operator': 'in', 'value': ['برنامه ریزی - نصب نگارش جدید'], 'active_only': False, 'priority': 1}


def seed(apps, schema_editor):
    Options = apps.get_model('integrations', 'ModuleSettings')
    Rule = apps.get_model('integrations', 'EvaluationRule')
    for options in Options.objects.using(schema_editor.connection.alias).filter(module__in=['planning', 'backlogs']):
        values = dict(READY if options.module == 'planning' else PROGRAM)
        code = values.pop('code')
        Rule.objects.using(schema_editor.connection.alias).get_or_create(settings=options, code=code, defaults=values)


class Migration(migrations.Migration):
    dependencies = [('integrations', '0010_modulesettings_report_scope')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
