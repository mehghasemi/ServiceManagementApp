from django.test import SimpleTestCase
from types import SimpleNamespace
from planning.visit_charts import visit_breakdown

class VisitChartTests(SimpleTestCase):
    def test_unknown_without_rules_and_city(self):
        rows=[{'crm_id':'1','customer_id':'a','customer':'A','evidence':{}},{'crm_id':'2','customer_id':'a','customer':'A','evidence':{}}]
        centers,cities=visit_breakdown(rows,[])
        self.assertEqual(centers[0]['total'],2)
        self.assertEqual(centers[0]['unknown'],2)
        self.assertEqual(cities[0]['total'],2)
    def test_completed_rule_counts_actual_matches(self):
        rule=SimpleNamespace(enabled=True,purpose='completed',active_only=False,metric='source_status',operator='in',value=['Visited'])
        rows=[{'crm_id':'1','customer_id':'a','customer':'A','source_status':'Visited','evidence':{'city':'X','state':1}}]
        centers,cities=visit_breakdown(rows,[rule])
        self.assertEqual(centers[0]['done'],1)
        self.assertEqual(cities[0]['label'],'X')

