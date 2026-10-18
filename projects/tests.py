import uuid
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, SimpleTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from integrations.models import CRMView, ProjectSnapshot, CRMCase, CaseAction
from integrations.jobs import configuration, module_settings, start_job, run_job, selection_key
from integrations.client import CRMError
from integrations.analysis import FORMAT
from .services import normalize_projects, dashboard_data
from .forms import ProjectForm


class ProjectTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('project-test', is_staff=True)
        self.client.force_login(self.user)
        self.scope = configuration().scope
        self.options = module_settings('projects')
        self.options.case_view = CRMView.objects.create(scope=self.scope, entity='brd_project', kind='userqueries', crm_id=uuid.uuid4(), name='Synthetic projects')
        self.options.note_view = CRMView.objects.create(scope=self.scope, entity='annotation', kind='savedqueries', crm_id=uuid.uuid4(), name='Synthetic notes')
        self.options.save()
        self.identifier = str(uuid.uuid4())

    def receive(self, fail=False):
        job = start_job(self.user, 'sync', launch=False, module='projects')
        def fetch(view, related_ids=None):
            if fail:
                raise CRMError('synthetic failure')
            if view['entity'] == 'brd_project':
                return ([{'brd_projectid': self.identifier, 'brd_name': 'Synthetic project', 'statecode': 0}], '', 'Synthetic projects')
            self.assertEqual(related_ids, [self.identifier])
            return ([{'annotationid': str(uuid.uuid4()), '_objectid_value': self.identifier, 'notetext': '<script>test</script>', 'modifiedon': '2026-01-01T00:00:00Z'}], '', 'Synthetic notes')
        with patch('integrations.jobs.Client.fetch_view', side_effect=fetch):
            run_job(job.pk)
        job.refresh_from_db()
        return job

    def test_row_refresh_changes_only_selected_project(self):
        self.receive()
        snapshot=ProjectSnapshot.objects.get()
        sibling=dict(snapshot.records[0], id=str(uuid.uuid4()), title='دیگری')
        snapshot.records.append(sibling); snapshot.save()
        old_stamp=snapshot.fetched_at
        job=start_job(self.user, 'row', module='projects', target=self.identifier, launch=False)
        def fetch(view, related_ids=None):
            self.assertEqual(related_ids,[self.identifier])
            return ([{'brd_projectid':self.identifier,'brd_name':'تازه','statecode':0}] if view['entity']=='brd_project' else [], '', '')
        with patch('integrations.jobs.Client.fetch_view',side_effect=fetch):
            run_job(job.pk)
        job.refresh_from_db();snapshot.refresh_from_db()
        self.assertEqual(job.status,'success')
        self.assertEqual(snapshot.records[0]['title'],'تازه')
        self.assertIn('refreshed_at',snapshot.records[0])
        self.assertEqual(snapshot.records[1],sibling)
        self.assertEqual(snapshot.fetched_at,old_stamp)

    def test_project_publish_failure_and_planning_isolation(self):
        planning = module_settings()
        self.assertEqual(self.receive().status, 'success')
        self.assertEqual(self.receive(fail=True).status, 'failed')
        self.assertEqual(ProjectSnapshot.objects.count(), 1)
        self.assertEqual(CRMCase.objects.count(), 0)
        planning.refresh_from_db()
        self.assertIsNone(planning.case_view_id)
        response = self.client.get('/projects/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total'], 1)
        response = self.client.get(f'/projects/{self.identifier}/')
        self.assertNotContains(response, '<script>test</script>')

    def test_selection_and_owner_isolate_snapshots(self):
        self.receive()
        other = get_user_model().objects.create_user('other-project', is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get('/projects/').context['total'], 0)
        self.assertEqual(self.client.get(f'/projects/{self.identifier}/').status_code, 404)
        self.client.force_login(self.user)
        self.options.note_view = None
        self.options.save()
        self.assertEqual(self.client.get('/projects/').context['total'], 0)

    def test_project_form_scopes_views(self):
        wrong = CRMView.objects.create(scope='other', entity='brd_project', kind='userqueries', crm_id=uuid.uuid4(), name='Other source')
        form = ProjectForm(instance=self.options, scope=self.scope)
        self.assertNotIn(wrong, form.fields['case_view'].queryset)
        self.assertNotIn('activity_view', form.fields)
        response = self.client.get('/projects/settings/')
        self.assertEqual(response.status_code, 200)


class ProjectMetricsTests(TestCase):
    def test_missing_notes_and_completed_project_not_overdue(self):
        from criteria.engine import ensure_rules
        today = timezone.localdate()
        options = module_settings('projects')
        base = {'id': str(uuid.uuid4()), 'status': 'Active', 'state': 0, 'planned_end': str(today-timedelta(days=3)), 'actual_end': None, 'manager': 'Manager', 'notes': []}
        rows, _, counts = dashboard_data([base], False, options, today)
        self.assertTrue(any(r.code == 'overdue' for r in rows[0]['attention_rules']))
        self.assertFalse(any(r.code in ('stale', 'no_note') for r in rows[0]['attention_rules']))
        base['status'] = 'Completed'
        rows, _, _ = dashboard_data([base], True, options, today)
        self.assertFalse(rows[0]['attention_rules'])
        base['status'] = 'Active'
        base['actual_end'] = str(today)
        rows, _, _ = dashboard_data([base], True, options, today)
        self.assertTrue(any(r.code == 'overdue' for r in rows[0]['attention_rules']))
        self.assertTrue(any(r.code == 'no_note' for r in rows[0]['attention_rules']))

    def test_note_matches_exact_project_and_deduplicates(self):
        identifier, other = str(uuid.uuid4()), str(uuid.uuid4())
        rows = [{'brd_projectid': identifier, 'brd_name': 'Synthetic', 'statuscode'+FORMAT: 'Active'}]*2
        notes = [{'annotationid': str(uuid.uuid4()), '_objectid_value': other, 'notetext': 'wrong'}]
        result = normalize_projects(rows, notes)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['notes'], [])


class GroupSuggestionTests(TestCase):
    def test_group_identity_and_conditional_effect(self):
        from planning.group_recommendations import grouped_recommendations
        user = get_user_model().objects.create_user('group-test')
        for customer in ['a', 'a', 'b', '']:
            CRMCase.objects.create(scope='test', crm_id=uuid.uuid4(), customer_id=customer, customer='Same title', parent_id='p', parent_title='ارتقاء به نسخه', source_status='Done', evidence={'state': 0})
        from criteria.engine import ensure_rules
        items = grouped_recommendations(CRMCase.objects.all(), user, timezone.localdate(), ensure_rules(module_settings()))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['count'], 2)
        self.assertEqual(items[0]['candidate'], 2)
        self.assertIn('قابل تعیین نیست', items[0]['condition'])
