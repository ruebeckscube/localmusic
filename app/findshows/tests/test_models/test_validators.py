from django.forms import ValidationError
from django.test import TestCase

from findshows.models import LabeledURLsValidator

class LabeledURLsValidatorTests(TestCase):
    def test_valid_input(self):
        try:
            LabeledURLsValidator()([('Label 1', 'http://www.testurl.com'), ('Label 2', 'http://www.another.net')])
        except ValidationError:
            self.fail("ValidationError raised for valid input")

    def test_mailto(self):
        LabeledURLsValidator()([('Label 1', 'mailto:user@email.com')])

    def test_no_display_name(self):
        with self.assertRaises(ValidationError):
            LabeledURLsValidator()([('Label', 'http://www.testurl.com'), ('', 'http://www.testurl.com')])

    def test_bad_url(self):
        with self.assertRaises(ValidationError):
            LabeledURLsValidator()([('Label', 'http://www.testurl.com'), ('Label 2', 'notaurl')])

    def test_not_a_list(self):
        with self.assertRaises(ValidationError):
            LabeledURLsValidator()('http://www.testurl.com')

    def test_not_a_tuple(self):
        with self.assertRaises(ValidationError):
            LabeledURLsValidator()([('Label', 'http://www.testurl.com'), 'http://www.testurl.com'])
