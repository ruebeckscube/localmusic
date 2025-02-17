from django.forms import ValidationError
from django.test import TestCase

from findshows.models import LabeledURLsValidator, MultiURLValidator

class LabeledURLsValidatorTests(TestCase):
    def test_valid_input(self):
        try:
            LabeledURLsValidator()([('Label 1', 'http://www.testurl.com'), ('Label 2', 'http://www.another.net')])
        except ValidationError:
            self.fail("ValidationError raised for valid input")

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


class MultiURLValidatorTests(TestCase):
    def test_valid_input(self):
        try:
            v = MultiURLValidator(MultiURLValidator.LISTEN, 3)
            v(" https://measuringmarigolds.bandcamp.com/track/was-it-worth-the-kiss \nhttps://measuringmarigolds.bandcamp.com/track/pardes-the-orchard\nhttps://measuringmarigolds.bandcamp.com/track/rather-be-a-stranger")
        except ValidationError:
            self.fail("ValidationError raised for valid input")

    def test_too_many_links(self):
        with self.assertRaises(ValidationError):
            v = MultiURLValidator(MultiURLValidator.LISTEN, 2)
            v("https://measuringmarigolds.bandcamp.com/track/was-it-worth-the-kiss\nhttps://measuringmarigolds.bandcamp.com/track/pardes-the-orchard\nhttps://measuringmarigolds.bandcamp.com/track/rather-be-a-stranger")

    def test_bad_url(self):
        with self.assertRaises(ValidationError):
            v = MultiURLValidator(MultiURLValidator.LISTEN, 3)
            v("https://measuringmarigolds.bandcamp.com/track/was-it-worth-the-kiss\nnotaurl")

    def test_bad_youtube_link(self):
        with self.assertRaises(ValidationError):
            v = MultiURLValidator(MultiURLValidator.YOUTUBE, 3)
            v("https://www.youtube.com/watch?vid=kC1bSJELPaQ")

    def test_unsupported_domain(self):
        with self.assertRaises(ValidationError):
            v = MultiURLValidator(MultiURLValidator.LISTEN, 3)
            v("https://deezer.page.link/ish5fTvfXEkuZD7o8")

    def test_different_domains(self):
        with self.assertRaises(ValidationError):
            v = MultiURLValidator(MultiURLValidator.LISTEN, 3)
            v("https://open.spotify.com/track/2mL1FLfUncO4UTAlDymUXQ?si=7e53f7f27c3f40c0\nhttps://measuringmarigolds.bandcamp.com/track/pardes-the-orchard")

    def test_bad_listen_link(self):
        with self.assertRaises(ValidationError):
            v = MultiURLValidator(MultiURLValidator.LISTEN, 3)
            v("https://open.spotify.com/track/2mL1FLfUncO4UTAlDymUXQ?si=7e53f7f27c3f40c0\nhttps://open.spotify.com/track/moreslugs/29BrlEPb8MaNYwBSovTpE4?si=66c8e11af7474230")

    def test_multiple_links__album(self):
        with self.assertRaises(ValidationError):
            v = MultiURLValidator(MultiURLValidator.LISTEN, 3)
            v("https://open.spotify.com/track/2mL1FLfUncO4UTAlDymUXQ?si=7e53f7f27c3f40c0\nhttps://open.spotify.com/track/29BrlEPb8MaNYwBSovTpE4?si=66c8e11af7474230\nhttps://open.spotify.com/album/52UVPYpWJtkadiJeIq6OSz?si=eEUWYO3BR8y7ivSbUi0G5A")
