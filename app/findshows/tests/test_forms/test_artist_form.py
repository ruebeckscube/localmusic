from unittest.mock import patch

from django.forms import ValidationError
from django.http import QueryDict
from findshows.models import EmbedLink, ListenLink, YoutubeLink
from findshows.forms import ArtistEditForm
from findshows.tests.test_helpers import TestCaseHelpers


class ArtistFormTestHelpers(TestCaseHelpers):
    def form_data(self, listen_links=None, youtube_links = []):
        self.create_musicbrainz_artist('1')
        self.create_musicbrainz_artist('2')
        self.create_musicbrainz_artist('3')
        data = {
            'name': ['This is a test with lots of extra text'],
            'bio': ['I sing folk songs and stuff'],
            'listen_links': listen_links if listen_links is not None else [
                'https://soundcloud.com/measuringmarigolds/was-it-worth-the-kiss-demo',
                'https://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo',
                'https://soundcloud.com/measuringmarigolds/wax-wane-demo'],
            'similar_musicbrainz_artists': ['1', '2', '3'],
            'socials_links_display_name': ['', '', ''],
            'socials_links_url': ['', '', ''],
            'initial-socials_links': ['[]'],
            'youtube_links': youtube_links
        }
        q = QueryDict('', mutable=True)
        for key, val_list in data.items():
            for val in val_list:
                q.appendlist(key, val)
        return q

    def file_data(self):
        return {
            'profile_picture': self.image_file(),
        }


class InitTests(ArtistFormTestHelpers):
    def test_from_instance(self):
        listen_links=['https://soundcloud.com/measuringmarigolds/was-it-worth-the-kiss-demo',
                      'https://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo']
        youtube_links=['https://www.youtube.com/watch?v=IC1ZuNDTiz8']
        artist = self.create_artist('chappell roan', listen_links=listen_links, youtube_links=youtube_links)
        form = ArtistEditForm(instance=artist)
        self.assertEqual(form['listen_links'].value(), listen_links)
        self.assertEqual(form['youtube_links'].value(), youtube_links)

    def test_new(self):
        form = ArtistEditForm()
        self.assertEqual(form['listen_links'].value(), [])
        self.assertEqual(form['youtube_links'].value(), [])


def mock_iframe(embed_link: EmbedLink):
    embed_link.iframe_url = embed_link.resource_url


@patch("findshows.forms.MusicBrainzArtist.get_similar_artists", return_value={"abc"})
class EmbedTests(ArtistFormTestHelpers):
    def test_valid_links(self, *args):
        form = ArtistEditForm(self.form_data(), self.file_data())
        self.assertTrue(form.is_valid())

    def test_empty_links(self, *args):
        form = ArtistEditForm(self.form_data(listen_links=[]), self.file_data())
        self.assertFalse(form.is_valid())
        self.assertIn("Please enter at least one", form.errors['listen_links'][0])

    @patch('findshows.forms.ListenLink.update_iframe_url', side_effect=mock_iframe, autospec=True)
    @patch('findshows.forms.YoutubeLink.update_iframe_url', side_effect=mock_iframe, autospec=True)
    def test_multiple_album_links(self, *args):
        listen_links = ["https://open.spotify.com/album/52UVPYpWJtkadiJeIq6OSz?si=eEUWYO3BR8y7ivSbUi0G5A",
                        "https://measuringmarigolds.bandcamp.com/album/measuring-marigolds"]
        form = ArtistEditForm(self.form_data(listen_links=listen_links), self.file_data())
        self.assertFalse(form.is_valid())
        self.assertIn("Please enter links to either (a) one album", form.errors['listen_links'][0])

    @patch('findshows.models.EmbedLink._get_oembed_iframe_url', side_effect=ValidationError("test error"))
    def test_error_from_update_iframe(self, *args):
        listen_links = ["https://open.spotify.com/album/52UVPYpWJtkadiJeIq6OSz?si=eEUWYO3BR8y7ivSbUi0G5A",
                        "https://measuringmarigolds.bandcamp.com/album/measuring-marigolds"]
        youtube_links = ["https://youtu.be/dQw4w9WgXcQ?si=qTRRfXlOMaGVdx1N"]
        form = ArtistEditForm(self.form_data(listen_links=listen_links, youtube_links=youtube_links), self.file_data())
        self.assertFalse(form.is_valid())
        self.assertIn("test error", form.errors['listen_links'][0])
        self.assertIn("test error", form.errors['youtube_links'][0])

    @patch('findshows.forms.ListenLink.update_iframe_url', side_effect=mock_iframe, autospec=True)
    @patch('findshows.forms.YoutubeLink.update_iframe_url', side_effect=mock_iframe, autospec=True)
    def test_update_embed_links(self, *args):
        listen_links=['https://soundcloud.com/measuringmarigolds/was-it-worth-the-kiss-demo',
                      'https://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo']
        youtube_links=['https://www.youtube.com/watch?v=IC1ZuNDTiz8']
        artist = self.create_artist('chappell roan', listen_links=listen_links, youtube_links=youtube_links)
        self.assert_records_created(ListenLink, 2)
        self.assert_records_created(YoutubeLink, 1)

        new_listen_links=["https://open.spotify.com/track/29BrlEPb8MaNYwBSovTpE4"]
        new_youtube_links=['https://www.youtube.com/watch?v=IC1ZuNDTiz8',
                           "https://www.youtube.com/watch?v=kC1bSJELPaQ"]
        form = ArtistEditForm(self.form_data(listen_links=new_listen_links,
                                             youtube_links=new_youtube_links),
                              self.file_data(),
                              instance=artist)
        self.assertTrue(form.is_valid())
        form.save()
        self.assert_records_created(ListenLink, 1)
        self.assert_records_created(YoutubeLink, 2)

        saved_listen_links = [l.resource_url for l in artist.listenlink_set.order_by('order')]
        saved_youtube_links = [l.resource_url for l in artist.youtubelink_set.order_by('order')]
        self.assertEqual(new_listen_links, saved_listen_links)
        self.assertEqual(new_youtube_links, saved_youtube_links)
