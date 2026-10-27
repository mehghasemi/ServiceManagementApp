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
        for change in [{'width':7},{'height':'9000px'},{'id':'<script>'},{'hidden':'false'}]:
            with self.subTest(change=change):
                widget={**self.widget(),**change}
                self.assertEqual(self.post('planning',{'revision':0,'widgets':[widget]}).status_code,400)
        row=PersonalDashboard.objects.create(user=self.user,key='custom-one',title='Mine')
        widget={**self.widget(True),'source':'http://evil'}
        self.assertEqual(self.post(row.key,{'revision':1,'widgets':[widget]}).status_code,400)
        self.assertEqual(self.post('planning',{'revision':0,'widgets':[self.widget(),self.widget()]}).status_code,400)
        self.assertEqual(self.post('unknown',{'revision':0,'widgets':[]}).status_code,404)
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
