import uuid
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from integrations.models import CRMView, BacklogSnapshot, CRMCase
from integrations.jobs import configuration,start_job,run_job
from planning.backlogs import options,DEFAULT_VIEW
from integrations.analysis import FORMAT

class BacklogTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('operator',is_staff=True)
        self.client.force_login(self.user)
        scope=configuration().scope
        self.view=CRMView.objects.create(scope=scope,kind='savedqueries',crm_id=uuid.uuid4(),entity='incident',name=DEFAULT_VIEW)
    def test_default_snapshot_notes_and_independence(self):
        opt=options();self.assertEqual(opt.case_view,self.view)
        opt.note_view=CRMView.objects.create(scope=opt.scope,kind='savedqueries',crm_id=uuid.uuid4(),entity='annotation',name='Synthetic notes');opt.save()
        identifier=str(uuid.uuid4())
        def fetch(view,related_ids=None):
            if view['entity']=='annotation':
                self.assertEqual(related_ids,[identifier])
                return [{'annotationid':str(uuid.uuid4()),'_objectid_value':identifier,'notetext':'note'}],'','Notes'
            return [{'incidentid':identifier,'title':'Backlog','_brd_caseservice_value':str(uuid.uuid4()),'_brd_caseservice_value'+FORMAT:'برنامه‌ریزی - نصب نگارش جدید'}],'<fetch><entity name="incident"/></fetch>',DEFAULT_VIEW
        job=start_job(self.user,'sync',module='backlogs',launch=False)
        with patch('integrations.jobs.Client.fetch_view',side_effect=fetch):run_job(job.pk)
        job.refresh_from_db();self.assertEqual(job.status,'success')
        row=BacklogSnapshot.objects.get().records[0]
        self.assertEqual(row['evidence']['case_service'],'برنامه‌ریزی - نصب نگارش جدید')
        self.assertEqual(len(row['evidence']['notes']),1)
        self.assertEqual(CRMCase.objects.count(),0)
        self.assertContains(self.client.get('/planning/backlogs/'),'برنامه‌ریزی - نصب نگارش جدید')
        other=get_user_model().objects.create_user('other',is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get('/planning/backlogs/'+identifier+'/').status_code,404)
    def test_user_view_is_not_overwritten(self):
        opt=options();other=CRMView.objects.create(scope=opt.scope,kind='savedqueries',crm_id=uuid.uuid4(),entity='incident',name='Chosen')
        opt.case_view=other;opt.save();self.assertEqual(options().case_view,other)
