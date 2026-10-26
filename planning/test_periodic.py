import uuid
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from integrations.jobs import configuration, start_job, run_job, selection_key
from integrations.models import CRMView, BacklogSnapshot
from planning.backlogs import options, snapshot_for

class PeriodicTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('tester',is_staff=True)
        self.client.force_login(self.user)
        self.scope=configuration().scope
        self.view=CRMView.objects.create(scope=self.scope,kind='savedqueries',crm_id=uuid.uuid4(),entity='incident',name='Synthetic visits')
        self.opt=options('periodic'); self.opt.case_view=self.view; self.opt.save()
    def row(self,month,city):
        return dict(crm_id=str(uuid.uuid4()),customer_id=str(uuid.uuid4()),customer='Synthetic',title='Visit',number='TEST',source_status='Open',evidence={'release':month,'city':city,'state':0,'case_service':''})
    def snapshot(self,rows,module='periodic'):
        opt=options(module);opt.case_view=self.view;opt.save()
        job=start_job(self.user,'sync',launch=False,module=module)
        job.status='success';job.save()
        return BacklogSnapshot.objects.create(owner=self.user,scope=self.scope,selection_key=selection_key(opt),job=job,source_name='Synthetic',records=rows)
    def test_shared_filters_dedup_and_city_links(self):
        a=self.row('M1','X');b=self.row('M1','');c=self.row('M2','Y')
        self.snapshot([a,a,b,c])
        response=self.client.get('/planning/visits/periodic/',{'month':'M1'})
        self.assertEqual(response.status_code,200)
        context=response.context
        self.assertEqual(context['total'],2)
        for key in ('status_chart','release_chart'):self.assertEqual(sum(r['count'] for r in context[key]),2)
        self.assertEqual(sum(r['total'] for r in context['city_chart']),2)
        self.assertEqual(context['page'].paginator.count,2)
        self.assertTrue(all('month=M1' in r['url'] for r in context['city_columns']['bars']))
        narrowed=self.client.get('/planning/visits/periodic/',{'month':'M1','city':'X'})
        self.assertEqual(narrowed.context['total'],1)
        self.assertEqual(self.client.get('/planning/visits/periodic/records/'+a['crm_id']+'/').status_code,200)
    def test_independent_snapshots_even_same_view(self):
        periodic=self.snapshot([self.row('M1','X')]);general=self.snapshot([self.row('M2','Y')],'backlogs')
        self.assertEqual(snapshot_for(self.user,'periodic'),periodic)
        self.assertEqual(snapshot_for(self.user),general)
        self.assertEqual(self.client.get('/planning/visits/periodic/').context['header_module'],'periodic')
    def test_publish_notes_and_failure_preserve_snapshot(self):
        previous=self.snapshot([self.row('M1','X')])
        job=start_job(self.user,'sync',launch=False,module='periodic')
        with patch('integrations.jobs.Client.fetch_view',side_effect=ValueError('Synthetic failure')):run_job(job.pk)
        self.assertEqual(snapshot_for(self.user,'periodic'),previous)
        job.refresh_from_db();self.assertEqual(job.status,'failed')
    def test_settings_preserve_general(self):
        general=options();before=general.case_view_id
        data={'case_view':self.view.pk,'revision':self.opt.revision,'confirm':'on','page_size':20,'auto_sync_enabled':'on','auto_sync_minutes':120,'report_scope':'monthly'}
        response=self.client.post('/planning/visits/periodic/settings/',data)
        self.assertEqual(response.status_code,302)
        self.opt.refresh_from_db();general.refresh_from_db()
        self.assertEqual(self.opt.auto_sync_minutes,120)
        self.assertEqual(self.opt.report_scope,'monthly')
        self.assertEqual(general.case_view_id,before)
    def test_periodic_scheduler_and_successful_publish(self):
        from integrations.scheduler import reserve_due
        pk=reserve_due()
        from integrations.models import SyncJob
        job=SyncJob.objects.get(pk=pk)
        self.assertEqual(job.config['module'],'periodic')
        identifier=str(uuid.uuid4())
        with patch('integrations.jobs.Client.fetch_view',return_value=([{'incidentid':identifier,'title':'Visit'}],'<fetch><entity name="incident"/></fetch>','Synthetic')):
            run_job(pk)
        self.assertEqual(len(snapshot_for(self.user,'periodic').records),1)
        self.assertIsNone(snapshot_for(self.user))
    def test_no_cross_user_detail_access(self):
        row=self.row('M1','X');self.snapshot([row])
        other=get_user_model().objects.create_user('other',is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get('/planning/visits/periodic/records/'+row['crm_id']+'/').status_code,404)
