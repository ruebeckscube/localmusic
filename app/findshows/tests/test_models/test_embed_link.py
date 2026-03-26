from unittest.mock import patch, MagicMock

from django.forms import ValidationError
from django.test import TestCase

from findshows.models import EmbedLink, ListenLink, YoutubeLink


EXAMPLE_SPOTIFY_RESOURCE_URL = "https://open.spotify.com/track/2mL1FLfUncO4UTAlDymUXQ?si=7e53f7f27c3f40c0"
EXAMPLE_SPOTIFY_RESPONSE = {'html': '<iframe style="border-radius: 12px" width="100%" height="152" title="Spotify Embed: It&apos;s Just Sunrise" frameborder="0" allowfullscreen allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy" src="https://open.spotify.com/embed/track/2mL1FLfUncO4UTAlDymUXQ?si=7e53f7f27c3f40c0&amp;utm_source=oembed"></iframe>'}
EXAMPLE_SPOTIFY_IFRAME_URL = "https://open.spotify.com/embed/track/2mL1FLfUncO4UTAlDymUXQ?si=7e53f7f27c3f40c0&utm_source=oembed"

EXAMPLE_BANDCAMP_RESOURCE_URL = "https://measuringmarigolds.bandcamp.com/track/was-it-worth-the-kiss"
EXAMPLE_BANDCAMP_RESPONSE = '''
<!DOCTYPE html>
<html   xmlns:og="http://opengraphprotocol.org/schema/"
        xmlns:fb="http://www.facebook.com/2008/fbml"
        lang="en">
<head>
    <title>Was It Worth the Kiss | Measuring Marigolds</title>

    <meta name="title" content="Was It Worth the Kiss, by Measuring Marigolds">
    <meta property="og:title" content="Was It Worth the Kiss, by Measuring Marigolds">
    <meta property="og:type" content="song">
    <meta property="og:video"
        content="https://bandcamp.com/EmbeddedPlayer/v=2/track=2959425971/size=large/tracklist=false/artwork=small/">
    <meta property="og:video:secure_url"
        content="https://bandcamp.com/EmbeddedPlayer/v=2/track=2959425971/size=large/tracklist=false/artwork=small/">
    <meta property="og:video:type" content="text/html">
    <meta property="og:video:height" content="120">
    <meta property="og:video:width" content="400">
</head>
<body>
</body
</html>
'''
EXAMPLE_BANDCAMP_IFRAME_URL = "https://bandcamp.com/EmbeddedPlayer/v=2/track=2959425971/size=medium/tracklist=false/artwork=small/"

EXAMPLE_YOUTUBE_RESOURCE_URL = "https://www.youtube.com/watch?v=kC1bSJELPaQ&embeds_referring_origin=http%3A%2F%2Fexample.com&source_ve_path=MjM4NTE"

@patch('findshows.models.requests.get')
class UpdateIframeUrlTests(TestCase):
    def set_mock_props(self, requests_mock, status_code, json={}, text=""):
        r = MagicMock(status_code=status_code)
        r.json.return_value = json
        r.text = text
        requests_mock.return_value = r

    def test_oembed_bad_http_response(self, requests_mock):
        link = ListenLink(resource_url = EXAMPLE_SPOTIFY_RESOURCE_URL)
        for code in (401, 403, 404, 500):
            self.set_mock_props(requests_mock, code)
            with self.assertRaises(ValidationError):
                link.update_iframe_url()

    def test_bandcamp_bad_http_response(self, requests_mock):
        link = ListenLink(resource_url = EXAMPLE_BANDCAMP_RESOURCE_URL)
        for code in (401, 403, 404, 500):
            self.set_mock_props(requests_mock, code)
            with self.assertRaises(ValidationError):
                link.update_iframe_url()

    def test_oembed_good_http_response_bad_content(self, requests_mock):
        link = ListenLink(resource_url = EXAMPLE_SPOTIFY_RESOURCE_URL)
        self.set_mock_props(requests_mock, 200)
        with self.assertRaises(ValidationError):
            link.update_iframe_url()

    def test_bandcamp_good_http_response_bad_content(self, requests_mock):
        link = ListenLink(resource_url = EXAMPLE_BANDCAMP_RESOURCE_URL)
        self.set_mock_props(requests_mock, 200)
        with self.assertRaises(ValidationError):
            link.update_iframe_url()

    def test_oembed_good_http_response_success(self, requests_mock):
        link = ListenLink(resource_url = EXAMPLE_SPOTIFY_RESOURCE_URL)
        self.set_mock_props(requests_mock, 200, json=EXAMPLE_SPOTIFY_RESPONSE)
        link.update_iframe_url()
        self.assertEqual(link.iframe_url, EXAMPLE_SPOTIFY_IFRAME_URL)

    def test_bandcamp_good_http_response_success(self, requests_mock):
        link = ListenLink(resource_url = EXAMPLE_BANDCAMP_RESOURCE_URL)
        self.set_mock_props(requests_mock, 200, text=EXAMPLE_BANDCAMP_RESPONSE)
        link.update_iframe_url()
        self.assertEqual(link.iframe_url, EXAMPLE_BANDCAMP_IFRAME_URL)

    def test_youtube_link_for_listen(self, requests_mock):
        link = ListenLink(resource_url = EXAMPLE_YOUTUBE_RESOURCE_URL)
        self.set_mock_props(requests_mock, 200, json=EXAMPLE_SPOTIFY_RESPONSE)
        with self.assertRaises(ValidationError):
            link.update_iframe_url()


class ResourceURLTests(TestCase):
    # Test platform variable being set, and link stripping
    def test_spotify(self):
        link = ListenLink(resource_url = "https://open.spotify.com/track/4ghNfXsbI1lMZGh4w4hqHO?go=1&sp_cid=e039b070a52b0a7025f1b7ac75da663e&utm_source=embed_player_p&utm_medium=desktop&nd=1&dlsi=45124487126c43a8&si=928305672398")
        self.assertEqual(link.resource_url, "https://open.spotify.com/track/4ghNfXsbI1lMZGh4w4hqHO")
        self.assertEqual(link.get_platform(), ListenLink.SPOTIFY)

    def test_soundcloud(self):
        link = ListenLink(resource_url = "https://soundcloud.com/measuringmarigolds/growin-slow?utm_source=clipboard&utm_medium=text&utm_campaign=social_sharing")
        self.assertEqual(link.resource_url, "https://soundcloud.com/measuringmarigolds/growin-slow")
        self.assertEqual(link.get_platform(), ListenLink.SOUNDCLOUD)

    def test_bandcamp(self):
        link = ListenLink(resource_url = "https://measuringmarigolds.bandcamp.com/track/pardes-the-orchard?from=embed")
        self.assertEqual(link.resource_url, "https://measuringmarigolds.bandcamp.com/track/pardes-the-orchard")
        self.assertEqual(link.get_platform(), ListenLink.BANDCAMP)

    def test_youtube(self):
        link = YoutubeLink(resource_url = "https://www.youtube.com/watch?v=kC1bSJELPaQ&list=RDkC1bSJELPaQ&start_radio=1&source_ve_path=239y2938&embeds_referring_origin=91284792318&si=91820748190327p")
        self.assertEqual(link.resource_url, "https://www.youtube.com/watch?v=kC1bSJELPaQ")
        self.assertEqual(link.get_platform(), EmbedLink.YOUTUBE)
