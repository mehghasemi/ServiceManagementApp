from django.test import SimpleTestCase, RequestFactory
from config.sorting import sort_rows

class SortingTests(SimpleTestCase):
    def test_numeric_missing_and_stable_ties(self):
        rows=[{'n':None,'id':0},{'n':10,'id':1},{'n':2,'id':2},{'n':2,'id':3}]
        request=RequestFactory().get('/',{'sort':'n','direction':'desc'})
        self.assertEqual([r['id'] for r in sort_rows(request,rows,{'n':'n'})],[1,2,3,0])
    def test_unknown_key_and_natural_text(self):
        rows=[{'n':'CAS-10'},{'n':'CAS-2'}]
        self.assertIs(sort_rows(RequestFactory().get('/',{'sort':'bad'}),rows,{'n':'n'}),rows)
        self.assertEqual(sort_rows(RequestFactory().get('/',{'sort':'n'}),rows,{'n':'n'})[0]['n'],'CAS-2')
    def test_header_preserves_filters_resets_page_and_escapes(self):
        from planning.templatetags.service_ui import sort_header
        request=RequestFactory().get('/',{'sort':'n','page':3,'q':'<script>','direction':'asc'})
        html=str(sort_header({'request':request},'n','عدد'))
        self.assertIn('direction=desc',html)
        self.assertNotIn('page=',html)
        self.assertIn('q=',html)
        self.assertNotIn('<script>',html)
