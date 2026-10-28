import json
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from planning.models import PersonalDashboard
from planning.dashboard_service import chart_data

class PersonalDashboardTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('dashboard-owner',is_staff=True)
        self.other=get_user_model().objects.create_user('dashboard-other',is_staff=True)
        self.client.force_login(self.user)
    def post(self,key,data):
        return self.client.post('/preferences/dashboards/'+key+'/',json.dumps(data),content_type='application/json')
    def widget(self,custom=False):
        result={'id':'w-one','width':6,'height':'normal','hidden':False}
        if custom:result.update(source='case-status',kind='ring')
        return result
    def test_create_rename_and_layout_survive(self):
        response=self.client.post('/dashboards/',{'title':'نمای خدمات'})
        self.assertEqual(response.status_code,302)
        row=PersonalDashboard.objects.get(user=self.user)
        self.assertEqual(self.post(row.key,{'revision':1,'title':'نام جدید','widgets':[self.widget(True)]}).status_code,200)
        row.refresh_from_db();self.assertEqual(row.title,'نام جدید');self.assertEqual(row.revision,2)
        self.assertEqual(self.client.get(response.url).status_code,200)
        self.assertContains(self.client.get(response.url),'dashboard-builder')
    @override_settings(SERVICE_LAN=True)
    def test_personal_scope_even_on_lan(self):
        row=PersonalDashboard.objects.create(user=self.other,key='custom-secret',title='Hidden')
        self.assertEqual(self.client.get('/dashboards/'+row.key+'/').status_code,404)
        self.assertEqual(self.client.get('/preferences/dashboards/'+row.key+'/').status_code,404)
        self.assertEqual(self.post(row.key,{'revision':1,'title':'Changed','widgets':[]}).status_code,404)
        self.assertNotContains(self.client.get('/dashboards/'),'Hidden')
    def test_builtin_revisions_prevent_lost_updates(self):
        data={'revision':0,'widgets':[self.widget()]}
        self.assertEqual(self.post('projects',data).status_code,200)
        self.assertEqual(self.post('projects',data).status_code,409)
        data['revision']=1;data['widgets'][0]['width']=12
        self.assertEqual(self.post('projects',data).status_code,200)
        self.assertEqual(self.client.get('/preferences/dashboards/projects/').json()['widgets'][0]['width'],12)
    def test_validation_rejects_arbitrary_data_and_sources(self):
        for change in [{'stack':'true'},{'width':7},{'height':'9000px'},{'id':'<script>'},{'hidden':'false'}]:
            with self.subTest(change=change):
                widget={**self.widget(),**change}
                self.assertEqual(self.post('planning',{'revision':0,'widgets':[widget]}).status_code,400)
        row=PersonalDashboard.objects.create(user=self.user,key='custom-one',title='Mine')
        widget={**self.widget(True),'source':'http://evil'}
        self.assertEqual(self.post(row.key,{'revision':1,'widgets':[widget]}).status_code,400)
        self.assertEqual(self.post('planning',{'revision':0,'widgets':[self.widget(),self.widget()]}).status_code,400)
        self.assertEqual(self.post('unknown',{'revision':0,'widgets':[]}).status_code,404)
    def test_mini_layout_roundtrip_preserves_existing_sizes(self):
        widgets=[dict(self.widget(),id='w-'+str(w),width=w,height='mini' if w<4 else 'compact') for w in (1,2,4,6,8,12)]
        self.assertEqual(self.post('projects',{'revision':0,'widgets':widgets}).status_code,200)
        self.assertEqual(self.client.get('/preferences/dashboards/projects/').json()['widgets'],widgets)

    def test_vertical_stack_saved_without_changing_legacy_widgets(self):
        widgets=[self.widget(),dict(self.widget(),id='w-two',stack=True,width=1)]
        self.assertEqual(self.post('projects',{'revision':0,'widgets':widgets}).status_code,200)
        self.assertEqual(self.client.get('/preferences/dashboards/projects/').json()['widgets'],widgets)

    def test_reset_keeps_dashboard_and_no_data_write(self):
        self.post('projects',{'revision':0,'widgets':[self.widget()]})
        self.assertEqual(self.post('projects',{'revision':1,'widgets':[]}).status_code,200)
        self.assertEqual(PersonalDashboard.objects.get().widgets,[])
    def test_anonymous_and_csrf(self):
        self.client.logout();self.assertEqual(self.client.get('/preferences/dashboards/home/').status_code,403)
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post('/preferences/dashboards/home/',json.dumps({'revision':0,'widgets':[]}),content_type='application/json').status_code,403)
    def test_empty_source_is_not_zero_activity(self):
        data=chart_data(self.user,[self.widget(True)])[0]
        self.assertIsNone(data['snapshot']);self.assertEqual(data['rows'],[])
    def test_title_escape_and_widget_cap(self):
        self.client.post('/dashboards/',{'title':'<script>alert(1)</script>'})
        row=PersonalDashboard.objects.get()
        self.assertNotContains(self.client.get('/dashboards/'+row.key+'/'),'<script>alert(1)</script>')
        self.assertEqual(self.post('projects',{'revision':0,'widgets':[dict(self.widget(),id='w-'+str(i)) for i in range(31)]}).status_code,400)

    @override_settings(CSRF_COOKIE_NAME='service_dev_csrf')
    def test_custom_csrf_cookie_accepts_dom_token(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        response=client.get('/preferences/dashboards/projects/')
        token=client.cookies['service_dev_csrf'].value
        response=client.post('/preferences/dashboards/projects/',json.dumps({'revision':0,'widgets':[self.widget()]}),content_type='application/json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,200)


class SharedDashboardTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_user('publishing-admin',is_staff=True,is_superuser=True)
        self.reader=get_user_model().objects.create_user('dashboard-reader',is_staff=True)
        self.draft=PersonalDashboard.objects.create(user=self.admin,key='custom-team',title='Team dashboard',widgets=[{'id':'w-one','width':6,'height':'normal','hidden':False,'source':'case-status','kind':'ring'}])
        self.client.force_login(self.admin)
    def publish(self,key='custom-team',expected=0,revision=1,enabled=True):
        return self.client.post('/preferences/dashboards/'+key+'/publish/',json.dumps({'revision':revision,'publication_revision':expected,'enabled':enabled}),content_type='application/json')
    def test_admin_publishes_readonly_snapshot(self):
        self.assertEqual(self.publish().status_code,200)
        self.draft.title='Unpublished change';self.draft.save()
        self.client.force_login(self.reader)
        response=self.client.get('/dashboards/shared/custom-team/')
        self.assertContains(response,'Team dashboard');self.assertNotContains(response,'Unpublished change')
        self.assertNotContains(response,'id="dashboard-builder"')
        self.assertContains(self.client.get('/dashboards/'),'Team dashboard')
    @override_settings(SERVICE_LAN=True)
    def test_staff_cannot_publish(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.publish().status_code,403)
    def test_builtin_inheritance_and_personal_override(self):
        PersonalDashboard.objects.create(user=self.admin,key='projects',widgets=[{'id':'w-one','width':12,'height':'tall','hidden':False}])
        self.assertEqual(self.publish('projects').status_code,200)
        self.client.force_login(self.reader)
        response=self.client.get('/preferences/dashboards/projects/').json()
        self.assertTrue(response['inherited']);self.assertEqual(response['widgets'][0]['width'],12)
        personal=PersonalDashboard.objects.create(user=self.reader,key='projects',widgets=[{'id':'w-one','width':4,'height':'compact','hidden':False}])
        self.assertFalse(self.client.get('/preferences/dashboards/projects/').json()['inherited'])
        personal.widgets=[];personal.save()
        self.assertTrue(self.client.get('/preferences/dashboards/projects/').json()['inherited'])
    def test_publish_concurrency_and_unpublish(self):
        self.assertEqual(self.publish().status_code,200)
        self.assertEqual(self.publish().status_code,409)
        self.assertEqual(self.publish(expected=1,enabled=False).status_code,200)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get('/dashboards/shared/custom-team/').status_code,404)
        self.assertNotContains(self.client.get('/dashboards/'),'Team dashboard')
    def test_publication_uses_viewer_data_scope(self):
        self.publish();self.client.force_login(self.reader)
        from unittest.mock import patch
        with patch('planning.dashboard_views.chart_data',return_value=[]) as adapter:
            self.assertEqual(self.client.get('/dashboards/shared/custom-team/').status_code,200)
            self.assertEqual(adapter.call_args.args[0].pk,self.reader.pk)
    def test_stale_draft_rejected(self):
        self.assertEqual(self.publish(revision=0).status_code,409)

    @override_settings(SERVICE_LAN=False)
    def test_existing_local_admin_contract(self):
        self.client.force_login(self.reader)
        self.assertTrue(self.client.get('/preferences/dashboards/projects/').json()['can_publish'])


class ChartBuilderTests(TestCase):
    def test_two_dimensions_keep_missing_and_filter(self):
        from planning.dashboard_service import aggregate
        records=[{'customer':'A','source_status':'Done'},{'customer':'A','source_status':'Done'},{'customer':'A','source_status':''},{'customer':'B','source_status':'Open'}]
        rows=aggregate(records,'backlog-customer','backlog-status')
        self.assertEqual(sum(r['count'] for r in rows),4)
        self.assertEqual(len(rows),3)
        self.assertTrue(any(r['series']=='نامشخص' for r in rows))
        self.assertEqual(sum(r['count'] for r in aggregate(records,'backlog-customer','backlog-status','A')),3)

    def test_chart_contract_rejects_cross_module_and_non_temporal_line(self):
        from planning.dashboard_views import validate_widgets
        base={'id':'w-report','width':6,'height':'normal','hidden':False,'source':'periodic-city','kind':'bars','split':'periodic-status','title':'شهر و وضعیت','contains':''}
        self.assertEqual(validate_widgets([base],True),[base])
        for changes in ({'split':'project-status'},{'kind':'line'},{'source':'__dict__'},{'contains':[]},{'kind':'script'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate_widgets([{**base,**changes}],True)

    def test_standard_distribution_types_render_safely(self):
        from django.template import Template,Context
        for kind in ('columns','bars','pie','ring'):
            output=Template('{% load dashboard_visuals %}{% distribution rows title kind %}').render(Context({'rows':[{'label':'<script>bad</script>','count':4},{'label':'B','count':2}],'title':'آزمون','kind':kind}))
            self.assertNotIn('<script>',output)
            self.assertIn('&lt;script&gt;',output)
        from planning.templatetags.dashboard_visuals import distribution
        self.assertEqual(distribution([{'label':'A','count':4}],'Test','pie')['rows'][0]['share'],100)
