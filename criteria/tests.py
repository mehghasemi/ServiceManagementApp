import uuid
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from integrations.jobs import module_settings, configuration, selection_key
from integrations.models import EvaluationRule, CRMCase, CRMView, PlanningSnapshot, SyncJob, SettingsAudit
from .engine import ensure_rules, matches, project_facts, evaluate_records
from planning.group_recommendations import grouped_recommendations


class CriteriaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('criteria-operator', is_staff=True)
        self.client.force_login(self.user)
        self.options = module_settings()
        self.options.case_view = CRMView.objects.create(scope=self.options.scope, entity='incident', kind='userqueries', crm_id=uuid.uuid4(), name='Synthetic cases')
        self.options.save()
        self.rules = ensure_rules(self.options)
        self.options.refresh_from_db()

    def test_attention_groups_are_saved_editable_and_filter_exactly(self):
        self.cases()
        rule = self.rule('resolution_review')
        self.assertEqual(rule.attention_group, 'clarification')
        page = self.client.get('/planning/attention/?group=clarification')
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context['page'].paginator.count > 0)
        for row in page.context['page']:
            self.assertTrue(any(r.attention_group == 'clarification' for r in row['rules']))
        rule.attention_group = 'decision'
        rule.save()
        page = self.client.get('/planning/attention/?group=decision')
        self.assertTrue(page.context['page'].paginator.count > 0)
        self.assertEqual(self.client.get('/planning/attention/?group=invalid').context['page'].paginator.count, 0)

    def rule(self, code):
        return self.options.rules.get(code=code)

    def cases(self):
        ids = []
        for index, (customer, parent, status) in enumerate([('a', 'p', 'Done'), ('a', 'p', 'Checking in Presence Services'), ('a', 'q', 'Checking in Presence Services'), ('b', 'p', 'Done'), ('', 'p', 'Done')]):
            case = CRMCase.objects.create(scope=self.options.scope, crm_id=uuid.uuid4(), number=str(index), customer_id=customer, customer='Synthetic same label', parent_id=parent, parent_title='ارتقاء به نسخه', source_status=status, evidence={'state': 0})
            ids.append(case.pk)
        job = SyncJob.objects.create(owner=self.user, scope=self.options.scope, kind='sync', status='success')
        snapshot = PlanningSnapshot.objects.create(owner=self.user, scope=self.options.scope, selection_key=selection_key(self.options), job=job)
        snapshot.cases.add(*ids)
        return CRMCase.objects.filter(pk__in=ids)

    def test_unlinked_queue_and_status_filter_remain_independent_of_grouping(self):
        cases=self.cases()
        linked=cases.first()
        linked.source_status='Planned';linked.save()
        unlinked=cases.last()
        unlinked.parent_id='';unlinked.source_status='Planned';unlinked.save()
        response=self.client.get('/planning/', {'parent_link':'missing','status':'Planned'})
        self.assertEqual(response.status_code,200)
        self.assertEqual([c.pk for c in response.context['page']], [unlinked.pk])
        self.assertEqual(response.context['unlinked_count'],1)
        response=self.client.get('/planning/', {'parent_link':'missing','status':'Other'})
        self.assertEqual(response.context['page'].paginator.count,0)

    def test_shared_upgrade_and_visit_without_local_actions(self):
        cases = self.cases()
        rows = grouped_recommendations(cases, self.user, timezone.localdate(), self.rules)
        self.assertEqual({r['rule'].code for r in rows}, {'upgrade', 'onsite'})
        self.assertTrue(all(r['count'] == 2 and r['customer_id'] == 'a' for r in rows))
        upgrade = next(r for r in rows if r['rule'].code == 'upgrade')
        visit = next(r for r in rows if r['rule'].code == 'onsite')
        self.assertEqual(upgrade['candidate'], 1)
        self.assertEqual(visit['candidate'], 0)
        self.assertEqual(visit['parent_id'], '')
        response = self.client.get('/planning/', {'customer': 'a', 'opportunity': visit['rule'].pk})
        self.assertEqual(response.context['page'].paginator.count, 2)

    def test_disable_and_minimum_changes_real_results_without_sync(self):
        cases = self.cases()
        rule = self.rule('upgrade')
        rule.min_count = 3
        rule.save()
        rows = grouped_recommendations(cases, self.user, timezone.localdate(), ensure_rules(self.options))
        self.assertFalse(any(r['rule'].code == 'upgrade' for r in rows))
        selected = [str(r.pk) for r in self.rules if r.code not in ('onsite', 'resolution_review') and r.enabled]
        response = self.client.post('/planning/criteria/', {'enabled': selected, 'revision': self.options.revision, 'confirm': 'on'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SettingsAudit.objects.filter(area='planning:rules').count(), 1)
        rows = grouped_recommendations(cases, self.user, timezone.localdate(), ensure_rules(self.options))
        self.assertEqual(rows, [])
        self.assertEqual(self.client.get('/planning/attention/').context['total'], 0)
        self.assertFalse(self.rule('resolution_review').enabled)

    def test_unknown_notes_not_zero_or_failure(self):
        options = module_settings('projects')
        rules = ensure_rules(options)
        row = {'id': 'synthetic', 'state': 0, 'status': 'In progress', 'planned_end': str(timezone.localdate()+timedelta(days=1)), 'manager': 'Synthetic', 'notes': []}
        facts = project_facts(row, options, False, timezone.localdate())
        hits, counts = evaluate_records([(row, facts)], rules)
        self.assertEqual(hits, [])
        self.assertTrue(all(c['unknown'] == 1 for c in counts if c['rule'].code in ('stale', 'no_note')))
        row['status'] = 'Completed'
        self.assertEqual(evaluate_records([(row, project_facts(row, options, True, timezone.localdate()))], rules)[0], [])

    def test_no_reseed_and_module_isolation(self):
        rule = self.rule('stale')
        rule.value = 7
        rule.enabled = False
        rule.save()
        ensure_rules(module_settings())
        rule.refresh_from_db()
        self.assertEqual(rule.value, 7)
        self.assertFalse(rule.enabled)
        project = module_settings('projects')
        ensure_rules(project)
        self.assertEqual(project.rules.get(code='stale').value, 30)
        self.assertEqual(self.client.get(f'/projects/criteria/{rule.pk}/').status_code, 404)

    def form_data(self, **changes):
        data = {'request_key': str(uuid.uuid4()), 'revision': 0, 'label': 'Synthetic new criterion', 'enabled': 'on', 'purpose': 'attention', 'metric': 'note_age', 'operator': 'gt', 'target_value': '7', 'priority': 2, 'active_only': 'on', 'grouping': 'customer_program', 'min_count': 2, 'action_title': '', 'impact': '', 'confirm': 'on'}
        data.update(changes)
        return data

    def test_new_rule_validates_audits_and_is_idempotent(self):
        data = self.form_data()
        self.assertEqual(self.client.post('/planning/criteria/new/', data).status_code, 302)
        self.assertEqual(self.client.post('/planning/criteria/new/', data).status_code, 302)
        self.assertEqual(EvaluationRule.objects.filter(label='Synthetic new criterion').count(), 1)
        self.assertEqual(SettingsAudit.objects.filter(area='planning:rule').count(), 1)
        data['target_value'] = '8'
        self.assertEqual(self.client.post('/planning/criteria/new/', data).status_code, 409)
        invalid = self.form_data(operator='contains_any')
        self.assertEqual(self.client.post('/planning/criteria/new/', invalid).status_code, 200)
        self.assertEqual(EvaluationRule.objects.filter(label='Synthetic new criterion').count(), 1)

    def test_revision_and_permissions(self):
        self.options.revision += 1
        self.options.save()
        response = self.client.post('/planning/criteria/', {'enabled': [], 'revision': self.options.revision-1, 'confirm': 'on'})
        self.assertEqual(response.status_code, 409)
        other = get_user_model().objects.create_user('criteria-reader', is_staff=False)
        self.client.force_login(other)
        self.assertEqual(self.client.get('/planning/criteria/').status_code, 403)
        self.assertEqual(self.client.get('/projects/attention/').status_code, 403)

    def test_criteria_and_attention_pages_render(self):
        self.cases()
        for path in ['/planning/criteria/', '/planning/criteria/new/', '/planning/attention/', '/projects/criteria/', '/projects/attention/', '/projects/']:
            self.assertEqual(self.client.get(path).status_code, 200, path)
