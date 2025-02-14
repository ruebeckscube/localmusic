from django.urls import reverse
from findshows.tests.test_helpers import TestCaseHelpers, create_musicbrainz_artist_t


class MusicbrainzArtistSearchTests(TestCaseHelpers):
    def test_handles_missing_params(self):
        response = self.client.get(reverse("findshows:musicbrainz_artist_search_results"))
        self.assertEquals(response.content, b'')


    def test_search(self):
        create_musicbrainz_artist_t('1', 'Wet Leg')
        create_musicbrainz_artist_t('2', 'Devo')
        create_musicbrainz_artist_t('3', 'Illuminati Hotties')

        query = 'nat hot'
        response = self.client.get(reverse("findshows:musicbrainz_artist_search_results"),
                                   data={'mb-search': query})
        self.assert_equal_as_sets([a.mbid for a in response.context['musicbrainz_artists']], ['3'])
