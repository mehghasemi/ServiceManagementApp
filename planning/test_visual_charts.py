from datetime import date
from types import SimpleNamespace
from django.test import SimpleTestCase
from .charts import creation_chart, status_ring

class VisualChartTests(SimpleTestCase):
    def test_current_cohorts_missing_future_and_old_are_not_trends(self):
        cases=[SimpleNamespace(evidence={'created_on':v}) for v in ['2026-10-25T05:00:00Z', '2020-01-01T00:00:00Z', None,'bad','2027-01-01T00:00:00Z']]
        result=creation_chart(cases,date(2026,10,25))
        self.assertEqual(result['sum'],1)
        self.assertEqual(result['unknown'],3)
        self.assertEqual(len(result['rows']),6)
        self.assertEqual(result['rows'][-1]['label'],'1405/08')
    def test_empty_series_safe(self):
        self.assertEqual(creation_chart([],date(2026,10,25))['sum'],0)
        self.assertEqual(status_ring([]),[])
    def test_ring_exact_shares(self):
        rows=status_ring([{'count':1},{'count':2}])
        self.assertAlmostEqual(sum(x['share'] for x in rows),100)
        self.assertEqual(rows[1]['offset'],-rows[0]['share'])
