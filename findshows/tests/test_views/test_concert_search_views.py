from datetime import timedelta
from django.urls import reverse
from django.views.generic.dates import timezone_today
from findshows.forms import ShowFinderForm
from findshows.models import ConcertTags, MusicBrainzArtist
from findshows.tests.test_helpers import TestCaseHelpers, concert_GET_params


class ConcertSearchTests(TestCaseHelpers):
    # Also tests helper function get_concert_search_defaults
    def test_default_search_not_logged_in(self):
        response = self.client.get(reverse('findshows:home'))
        data = {key: val() if callable(val) else val
                for key, val in response.context['search_form'].initial.items()}
        self.assertEqual(data, {
            'date': timezone_today(),
            'end_date': timezone_today(),
            'is_date_range': False,
            'concert_tags': [t.value for t in ConcertTags]
        })


    def test_default_search_logged_in(self):
        mba = self.create_musicbrainz_artist('22', 'Jim Croce')
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        user_profile.favorite_musicbrainz_artists.add(mba)
        user_profile.preferred_concert_tags = [ConcertTags.ORIGINALS]
        user_profile.save()

        response = self.client.get(reverse('findshows:home'))
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
        self.create_musicbrainz_artist('22', 'Jim Croce')
        self.create_musicbrainz_artist('35', 'Jimmy Buffet')
        tomorrow = timezone_today() + timedelta(1)
        get_params = concert_GET_params(tomorrow, tomorrow, False,
                                        ['22','35'], [ConcertTags.ORIGINALS])
        response = self.client.get(reverse('findshows:concert_search'), get_params)
        data = response.context['search_form'].initial

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
        response = self.client.get(reverse('findshows:concert_search'))
        self.assertEqual(response.context['concerts'], [])
        self.assert_blank_form(response.context['search_form'], ShowFinderForm)


    def test_date_filtering(self):
        concert1 = self.create_concert(timezone_today() + timedelta(1))
        concert2 = self.create_concert(timezone_today() + timedelta(1))
        concert3 = self.create_concert(timezone_today() + timedelta(3))

        get_params = concert_GET_params(timezone_today() + timedelta(1))

        response = self.client.get(reverse('findshows:concert_search'), get_params)
        self.assert_equal_as_sets(response.context['concerts'], [concert1, concert2])


    def test_date_range_filtering(self):
        concert1 = self.create_concert(timezone_today())
        concert2 = self.create_concert(timezone_today() + timedelta(1))
        concert3 = self.create_concert(timezone_today() + timedelta(3))
        concert4 = self.create_concert(timezone_today() + timedelta(4))

        get_params = concert_GET_params(timezone_today() + timedelta(1),
                                        timezone_today() + timedelta(3),
                                        True)
        response = self.client.get(reverse('findshows:concert_search'), get_params)
        self.assert_equal_as_sets(response.context['concerts'], [concert2, concert3])


    def test_concert_tags_filtering(self):
        concert1 = self.create_concert(tags=[ConcertTags.ORIGINALS])
        concert2 = self.create_concert(tags=[ConcertTags.ORIGINALS, ConcertTags.COVERS])
        concert3 = self.create_concert(tags=[ConcertTags.DJ, ConcertTags.COVERS])
        concert4 = self.create_concert(tags=[ConcertTags.DJ])

        response = self.client.get(reverse('findshows:concert_search'),
                                   concert_GET_params(concert_tags=[ConcertTags.ORIGINALS]))
        self.assert_equal_as_sets(response.context['concerts'], [concert1, concert2])

        response = self.client.get(reverse('findshows:concert_search'),
                                   concert_GET_params(concert_tags=[ConcertTags.ORIGINALS, ConcertTags.COVERS]))
        self.assert_equal_as_sets(response.context['concerts'], [concert1, concert2, concert3])

        response = self.client.get(reverse('findshows:concert_search'),
                                   concert_GET_params(concert_tags=[]))
        self.assert_equal_as_sets(response.context['concerts'], [concert1, concert2, concert3, concert4])


    def test_temp_artist_filtering(self):
        non_temp_artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        temp_artist = self.get_static_instance(self.StaticArtists.TEMP_ARTIST)
        # at least one temp artist
        concert1 = self.create_concert(timezone_today() + timedelta(1), artists=[temp_artist, non_temp_artist])
        # no temp artists
        concert2 = self.create_concert(timezone_today() + timedelta(1))

        get_params = concert_GET_params(timezone_today() + timedelta(1))

        response = self.client.get(reverse('findshows:concert_search'), get_params)
        self.assert_equal_as_sets(response.context['concerts'], [concert2])


    def test_venue_filtering(self):
        unverified_concert=self.create_concert(venue=self.create_venue(is_verified=False, declined_listing=False))
        declined_concert=self.create_concert(venue=self.create_venue(is_verified=True, declined_listing=True))
        verified_concert=self.create_concert(venue=self.create_venue(is_verified=True, declined_listing=False))

        response = self.client.get(reverse('findshows:concert_search'), concert_GET_params())
        self.assert_equal_as_sets(response.context['concerts'], [verified_concert])


    def test_cancelled_concert_filtering(self):
        concert1 = self.create_concert()
        concert2 = self.create_concert(cancelled=True)
        response = self.client.get(reverse('findshows:concert_search'), concert_GET_params())
        self.assert_equal_as_sets(response.context['concerts'], [concert1])


    # Similarity sorting is tested in ../test_recommendations.py
