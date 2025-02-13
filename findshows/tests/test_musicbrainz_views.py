from django.urls import reverse
from findshows.tests.test_helpers import TestCaseHelpers, populate_musicbrainz_artists_t


class MusicbrainzArtistSearchTests(TestCaseHelpers):
    def test_handles_missing_params(self):
        response = self.client.get(reverse("findshows:musicbrainz_artist_search_results"))
        self.assertEquals(response.content, b'')


    def test_search(self):
        populate_musicbrainz_artists_t()
        query = 'nat hot'
        response = self.client.get(reverse("findshows:musicbrainz_artist_search_results"),
                                   data={'mb-search': query})
        self.assert_equal_as_sets([a.mbid for a in response.context['musicbrainz_artists']],
                                  ['92de1f8d-833e-47d0-ba85-02a03c81848a'])
