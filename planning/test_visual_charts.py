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

    def test_custom_range_and_partial_month(self):
        cases=[SimpleNamespace(evidence={'created_on':v}) for v in ['2024-04-01T00:00:00Z','2026-10-01T00:00:00Z','2026-10-20T00:00:00Z']]
        result=creation_chart(cases,date(2026,10,25),'2024-04-01','2026-10-10')
        self.assertEqual(result['sum'],2)
        self.assertGreater(len(result['rows']),6)
        self.assertIn('trend_from=',result['rows'][0]['url'])
        self.assertTrue(creation_chart(cases,date(2026,10,25),'bad')['error'])
    def test_ring_exact_shares(self):
        rows=status_ring([{'count':1},{'count':2}])
        self.assertAlmostEqual(sum(x['share'] for x in rows),100)
        self.assertEqual(rows[1]['offset'],-rows[0]['share'])


class DistributionPresentationTests(SimpleTestCase):
    def render_chart(self, rows, kind='ring'):
        from django.template.loader import render_to_string
        from planning.templatetags.dashboard_visuals import distribution
        return render_to_string('visuals/distribution.html', distribution(rows, 'آزمون', kind))

    def test_single_category_preserves_count_link_and_does_not_draw_chart(self):
        html = self.render_chart([{'label':'نمونه','count':7,'url':'?month=1405-08&status=x'}])
        self.assertIn('single-category', html)
        self.assertIn('month=1405-08&amp;status=x', html)
        self.assertIn('>7<', html)
        self.assertNotIn('<svg', html)

    def test_unknown_and_empty_are_distinct(self):
        unknown = self.render_chart([{'label':'نامشخص','count':7}])
        empty = self.render_chart([])
        self.assertIn('data-quality-state', unknown)
        self.assertNotIn('single-category', unknown)
        self.assertIn('visual-empty', empty)

    def test_bar_drilldowns_preserve_links_in_overflow_categories(self):
        rows=[{'label':str(i),'count':i+1,'url':f'?month=1405-08&city={i}'} for i in range(10)]
        html=self.render_chart(rows,'bars')
        for i in range(10):
            self.assertIn(f'?month=1405-08&amp;city={i}',html)
