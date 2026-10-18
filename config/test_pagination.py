from django.test import SimpleTestCase, RequestFactory
from .pagination import display_page_size

class DisplayPaginationTests(SimpleTestCase):
    def test_bounded_sizes(self):
        factory = RequestFactory()
        for value, expected in [('', 10), ('20', 20), ('50', 50), ('-1', 10), ('999999', 10), ('bad', 10)]:
            with self.subTest(value=value):
                self.assertEqual(display_page_size(factory.get('/', {'page_size': value}), 30), expected)
