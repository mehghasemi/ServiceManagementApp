from django.test import TestCase, SimpleTestCase
from django.contrib.auth import get_user_model
from django.template.loader import get_template
from pathlib import Path
from planning.templatetags.dashboard_visuals import distribution

class ChartGeometryTests(SimpleTestCase):
    def test_geometry_preserves_all_categories_and_unknown(self):
        original=[{'label':'A','count':3},{'label':'نامشخص','count':1},{'label':'Zero','count':0}]
        result=distribution(original,'Test')
        self.assertEqual(result['total'],4)
        self.assertEqual([r['share'] for r in result['rows']],[75,25,0])
        self.assertEqual([r['offset'] for r in result['rows']],[0,-75,-100])
        self.assertNotIn('share',original[0])
    def test_empty_is_not_percentage(self):
        result=distribution([],'Test')
        self.assertEqual(result['total'],0)
        self.assertEqual(result['rows'],[])
    def test_all_templates_compile(self):
        from django.conf import settings
        for path in (settings.BASE_DIR/'templates').rglob('*.html'):
            with self.subTest(path=path.name):
                get_template(path.relative_to(settings.BASE_DIR/'templates').as_posix())

class VisualPagesTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('visual-test',is_staff=True,is_superuser=True)
        self.client.force_login(self.user)
    def test_primary_pages_render_without_source(self):
        for path in ['/', '/planning/', '/planning/today/', '/planning/upgrades/',
                     '/planning/backlogs/', '/planning/visits/onsite/', '/planning/visits/periodic/',
                     '/planning/attention/', '/planning/suggestions/', '/planning/actions/',
                     '/projects/', '/projects/attention/', '/settings/', '/settings/backups/']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.status_code,200)
                self.assertContains(response,'visual-workspace.css')
    def test_evidence_keeps_native_details_and_grid(self):
        for path in ['/planning/upgrades/','/projects/','/planning/backlogs/']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertContains(response,'evidence-disclosure')
                self.assertContains(response,'data-grid=')
    def test_graph_labels_escaped(self):
        from django.template import Template,Context
        result=Template('{% load dashboard_visuals %}{% distribution rows "Test" %}').render(Context({'rows':[{'label':'<script>bad()</script>','count':1}]}))
        self.assertNotIn('<script>',result)
        self.assertIn('&lt;script&gt;',result)
