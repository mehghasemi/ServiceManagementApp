from types import SimpleNamespace
from django.test import SimpleTestCase
from .upgrade_analysis import customer_rows

class UpgradeTests(SimpleTestCase):
    def test_saved_rule_minimum_and_unknown_version(self):
        rule=SimpleNamespace(enabled=True,active_only=True,metric='has_parent',operator='eq',value=True,min_count=2,grouping='customer_program')
        case=SimpleNamespace(pk=1,customer_id='a',customer='مرکز',parent_id='b',evidence={})
        records=[(case,{'active':True,'has_parent':True})]
        row=customer_rows(records,rule)[0]
        self.assertEqual(row['count'],0)
        self.assertFalse(row['version_known'])
        rule.min_count=1
        self.assertEqual(customer_rows(records,rule)[0]['count'],1)
        self.assertTrue(customer_rows(records,rule)[0]['qualifies'])

    def test_disabled_rule_never_qualifies(self):
        rule=SimpleNamespace(enabled=False,active_only=True,metric='has_parent',operator='eq',value=True,min_count=1,grouping='customer')
        case=SimpleNamespace(pk=1,customer_id='a',customer='مرکز',parent_id='b',evidence={'automation_version':'Fonix-12.1'})
        row=customer_rows([(case,{'active':True,'has_parent':True})],rule)[0]
        self.assertFalse(row['qualifies'])
        self.assertEqual(row['current'],'Fonix-12.1')
