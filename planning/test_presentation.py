from datetime import timedelta
from types import SimpleNamespace
from django.test import SimpleTestCase
from django.utils import timezone
from planning.templatetags.service_ui import elapsed, case_timing
from criteria.help import explain_rule

class PresentationTests(SimpleTestCase):
    def test_elapsed_missing_future_today_and_days(self):
        today=timezone.localdate()
        self.assertEqual(elapsed(None), 'تاریخ نامشخص')
        self.assertEqual(elapsed('bad'), 'تاریخ نامشخص')
        self.assertEqual(elapsed(today.isoformat()), 'امروز')
        self.assertEqual(elapsed((today-timedelta(days=12)).isoformat()), '12 روز')
        self.assertIn('آینده', elapsed((today+timedelta(days=1)).isoformat()))

    def test_notes_distinguish_unfetched_empty_and_invalid(self):
        case=SimpleNamespace(evidence={'state':0, 'notes':[{'date':'invalid'}]})
        self.assertFalse(case_timing(case,False)['loaded'])
        self.assertTrue(case_timing(case,True)['has_notes'])
        self.assertIsNone(case_timing(case,True)['last_note'])
        case.evidence['notes']=[{'date':'2026-10-02T23:00:00Z'}, {'date':'2026-10-01T12:00:00Z'}]
        self.assertEqual(case_timing(case,True)['last_note'],'2026-10-03')
        case.evidence['state']=1
        self.assertFalse(case_timing(case,True)['active'])

    def test_help_tracks_saved_threshold_grouping_and_effect(self):
        rule=SimpleNamespace(settings=SimpleNamespace(module='planning'), metric='note_age', value=7,operator='gte',active_only=True,purpose='opportunity',grouping='customer',min_count=4,action_title='پیگیری مشترک',label='تست',priority=2,impact='کاهش دوباره‌کاری',closure_candidate=False)
        text=explain_rule(rule)
        self.assertIn('«7»',text); self.assertIn('حداقل 4 کیس',text);self.assertIn('کاهش دوباره‌کاری',text)
        rule.value=19
        self.assertIn('«19»',explain_rule(rule))
