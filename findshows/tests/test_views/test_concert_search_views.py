from datetime import timedelta
from django.urls import reverse
from django.views.generic.dates import timezone_today
from findshows.forms import ShowFinderForm
from findshows.models import ConcertTags, MusicBrainzArtist
from findshows.tests.test_helpers import TestCaseHelpers, create_artist_t, create_concert_t, create_musicbrainz_artist_t


def concert_GET_params(date=timezone_today(),
                       end_date=timezone_today(),
                       is_date_range=False,
                       musicbrainz_artists=[],
                       concert_tags=[t.value for t in ConcertTags]):
    return {
        'date': date.isoformat(),
        'end_date': end_date.isoformat(),
        'is_date_range': 'true' if is_date_range else 'false',
        'musicbrainz_artists': musicbrainz_artists,
        'concert_tags': concert_tags
    }


class ConcertSearchTests(TestCaseHelpers):
    # Also tests helper function get_concert_search_defaults
    def test_default_search_not_logged_in(self):
        response = self.client.get(reverse('findshows:concert_search'))
        data = {key: val() if callable(val) else val
                for key, val in response.context['search_form'].initial.items()}
        self.assertEqual(data, {
            'date': timezone_today(),
            'end_date': timezone_today(),
            'is_date_range': False,
            'concert_tags': [t.value for t in ConcertTags]
        })


    def test_default_search_logged_in(self):
        create_musicbrainz_artist_t('22', 'Jim Croce')
        self.create_and_login_non_artist_user(
            favorite_musicbrainz_artists=['22'],
            preferred_concert_tags=[ConcertTags.ORIGINALS]
        )

        response = self.client.get(reverse('findshows:concert_search'))
        data = {key: val() if callable(val) else val
                for key, val in response.context['search_form'].initial.items()}

        self.assert_equal_as_sets(data['musicbrainz_artists'], MusicBrainzArtist.objects.all()) # equality acting weird
        del data['musicbrainz_artists']
        self.assertEqual(data, {
            'date': timezone_today(),
            'end_date': timezone_today(),
            'is_date_range': False,
            'concert_tags': [ConcertTags.ORIGINALS.value],
        })


    def test_search_GET(self):
        create_musicbrainz_artist_t('22', 'Jim Croce')
        create_musicbrainz_artist_t('35', 'Jimmy Buffet')
        tomorrow = timezone_today() + timedelta(1)
        get_params = concert_GET_params(tomorrow, tomorrow, False,
                                        ['22','35'], [ConcertTags.ORIGINALS])
        response = self.client.get(reverse('findshows:concert_search'), get_params)
        data = response.context['search_form'].cleaned_data

        self.assert_equal_as_sets(data['musicbrainz_artists'], MusicBrainzArtist.objects.all()) # equality acting weird
        del data['musicbrainz_artists']
        self.assertEqual(data, {
            'date': tomorrow,
            'end_date': tomorrow,
            'is_date_range': False,
            'concert_tags': [ConcertTags.ORIGINALS.value],
        })


class ConcertSearchResultsTests(TestCaseHelpers):
    def test_no_GET_data(self):
        response = self.client.get(reverse('findshows:concert_search_results'))
        self.assertEqual(response.context['concerts'], [])
        self.assert_blank_form(response.context['search_form'], ShowFinderForm)


    def test_date_filtering(self):
        concert1 = create_concert_t(timezone_today() + timedelta(1))
        concert2 = create_concert_t(timezone_today() + timedelta(1))
        concert3 = create_concert_t(timezone_today() + timedelta(3))

        get_params = concert_GET_params(timezone_today() + timedelta(1))

        response = self.client.get(reverse('findshows:concert_search_results'), get_params)
        self.assert_equal_as_sets(response.context['concerts'], [concert1, concert2])


    def test_date_range_filtering(self):
        concert1 = create_concert_t(timezone_today())
        concert2 = create_concert_t(timezone_today() + timedelta(1))
        concert3 = create_concert_t(timezone_today() + timedelta(3))
        concert4 = create_concert_t(timezone_today() + timedelta(4))

        get_params = concert_GET_params(timezone_today() + timedelta(1),
                                        timezone_today() + timedelta(3),
                                        True)
        response = self.client.get(reverse('findshows:concert_search_results'), get_params)
        self.assert_equal_as_sets(response.context['concerts'], [concert2, concert3])


    def test_concert_tags_filtering(self):
        concert1 = create_concert_t(tags=[ConcertTags.ORIGINALS])
        concert2 = create_concert_t(tags=[ConcertTags.ORIGINALS, ConcertTags.COVERS])
        concert3 = create_concert_t(tags=[ConcertTags.DJ, ConcertTags.COVERS])
        concert4 = create_concert_t(tags=[ConcertTags.DJ])

        response = self.client.get(reverse('findshows:concert_search_results'),
                                   concert_GET_params(concert_tags=[ConcertTags.ORIGINALS]))
        self.assert_equal_as_sets(response.context['concerts'], [concert1, concert2])

        response = self.client.get(reverse('findshows:concert_search_results'),
                                   concert_GET_params(concert_tags=[ConcertTags.ORIGINALS, ConcertTags.COVERS]))
        self.assert_equal_as_sets(response.context['concerts'], [concert1, concert2, concert3])

        response = self.client.get(reverse('findshows:concert_search_results'),
                                   concert_GET_params(concert_tags=[]))
        self.assert_equal_as_sets(response.context['concerts'], [concert1, concert2, concert3, concert4])


    def test_temp_artist_filtering(self):
        non_temp_artist = create_artist_t()
        temp_artist = create_artist_t(is_temp_artist=True)
        # at least one temp artist
        concert1 = create_concert_t(timezone_today() + timedelta(1), artists=[temp_artist, non_temp_artist])
        # no temp artists
        concert2 = create_concert_t(timezone_today() + timedelta(1))

        get_params = concert_GET_params(timezone_today() + timedelta(1))

        response = self.client.get(reverse('findshows:concert_search_results'), get_params)
        self.assert_equal_as_sets(response.context['concerts'], [concert2])


    def test_similarity_sorting(self):
    # Setting up clusters of similar MusicBrainz artists, where each artist
        # is .7 similar to other artists in its cluster and unrelated to other clusters.
        # each artist has mbid/is named <cluster number>-<artist number> for easy referencing.
        # e.g. 0-0, 0-2 are in the same cluster, 1-0 is in a different cluster
        clusters = 4
        mb_artists_per_cluster = 3
        for c in range(clusters):
            for a in range(mb_artists_per_cluster):
                mbid = f'{c}-{a}'
                similar_mbids = (f'{c}-{a_s}'
                                 for a_s in range(mb_artists_per_cluster)
                                 if a_s != a)
                create_musicbrainz_artist_t(mbid, mbid, {s_mbid: .7 for s_mbid in similar_mbids})

        # Creating (local) artists that are similar to each cluster
        artist_0_0 = create_artist_t("Cluster-0 Artist-0", similar_musicbrainz_artists=[f'{0}-{a}' for a in range(3)])
        artist_0_1 = create_artist_t("Cluster-0 Artist-1", similar_musicbrainz_artists=[f'{0}-{a}' for a in range(3)])
        artist_0_2 = create_artist_t("Cluster-0 Artist-2", similar_musicbrainz_artists=[f'{0}-{a}' for a in range(3)])
        artist_1_0 = create_artist_t("Cluster-1 Artist-0", similar_musicbrainz_artists=[f'{1}-{a}' for a in range(3)])
        artist_1_1 = create_artist_t("Cluster-1 Artist-1", similar_musicbrainz_artists=[f'{1}-{a}' for a in range(3)])
        artist_2_0 = create_artist_t("Cluster-2 Artist-0", similar_musicbrainz_artists=[f'{2}-{a}' for a in range(3)])
        artist_2_1 = create_artist_t("Cluster-2 Artist-1", similar_musicbrainz_artists=[f'{2}-{a}' for a in range(3)])
        artist_3_0 = create_artist_t("Cluster-3 Artist-0", similar_musicbrainz_artists=[f'{3}-{a}' for a in range(3)])

        concert1 = create_concert_t(artists=[artist_0_0, artist_0_1, artist_0_2])
        concert2 = create_concert_t(artists=[artist_0_0, artist_0_1, artist_1_0])
        concert3 = create_concert_t(artists=[artist_0_0, artist_1_0, artist_1_1])
        concert4 = create_concert_t(artists=[artist_2_0, artist_2_1, artist_3_0])

        response = self.client.get(reverse('findshows:concert_search_results'),
                                   concert_GET_params(musicbrainz_artists=['0-0', '0-1']))
        self.assertEqual(response.context['concerts'], [concert1, concert2, concert3, concert4])

        response = self.client.get(reverse('findshows:concert_search_results'),
                                   concert_GET_params(musicbrainz_artists=['1-2']))
        self.assertEqual(response.context['concerts'][:2], [concert3, concert2])

        response = self.client.get(reverse('findshows:concert_search_results'),
                                   concert_GET_params(musicbrainz_artists=['2-0']))
        self.assertEqual(response.context['concerts'][0], concert4)

        # Results are random, just checking it doesn't error out
        response = self.client.get(reverse('findshows:concert_search_results'),
                                   concert_GET_params(musicbrainz_artists=['']))
