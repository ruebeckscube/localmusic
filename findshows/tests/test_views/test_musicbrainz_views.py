from django.urls import reverse
from findshows.tests.test_helpers import TestCaseHelpers


class MusicbrainzArtistSearchTests(TestCaseHelpers):
    def test_handles_missing_params(self):
        response = self.client.get(reverse("findshows:musicbrainz_artist_search_results"))
        self.assertEqual(response.content, b'')


    def test_search(self):
        self.create_musicbrainz_artist('1', 'Wet Leg')
        self.create_musicbrainz_artist('2', 'Devo')
        self.create_musicbrainz_artist('3', 'Illuminati Hotties')

        query = 'devo'
        response = self.client.get(reverse("findshows:musicbrainz_artist_search_results"),
                                   data={'mb-search': query})
        self.assert_equal_as_sets([a.mbid for a in response.context['musicbrainz_artists']], ['2'])
