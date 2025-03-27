import datetime
import json

from django.conf import settings
from django.urls import reverse
from django.views.generic.dates import timezone_today
from findshows.forms import ConcertForm

from findshows.models import Concert, Venue
from findshows.tests.test_helpers import TestCaseHelpers
from findshows.views import records_created_today


class ConcertViewTestHelpers(TestCaseHelpers):
    def concert_post_request(self, artist):
        return {'date': (timezone_today() + datetime.timedelta(3)).isoformat(),
                'doors_time_hour': ['8'],
                'doors_time_minutes': ['00'],
                'doors_time_ampm': ['pm'],
                'start_time_hour': ['8'],
                'start_time_minutes': ['30'],
                'start_time_ampm': ['pm'],
                'end_time_hour': ['11'],
                'end_time_minutes': ['30'],
                'end_time_ampm': ['pm'],
                'venue': [str(self.StaticVenues.DEFAULT_VENUE.value)],
                'ticket_link': ['https://www.thisisthevalueforconcertpostrequests.com'],
                'ticket_description': ['$10 suggested'],
                'poster': self.image_file(),
                'bill': json.dumps([{"id":artist.pk,"name":artist.name}]),
                'tags': ['OG']
                }


class ViewConcertTests(ConcertViewTestHelpers):
    def test_concert_exists(self):
        concert = self.create_concert()
        response = self.client.get(reverse("findshows:view_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/view_concert.html')
        self.assertEqual(response.context["concert"], concert)

    def test_concert_doesnt_exist(self):
        response = self.client.get(reverse("findshows:view_concert", args=(1,)))
        self.assertEqual(response.status_code, 404)

    def test_concert_with_temp_artist_is_only_viewable_by_artists_on_bill(self):
        concert = self.create_concert(artists=[self.get_static_instance(self.StaticArtists.LOCAL_ARTIST),
                                            self.get_static_instance(self.StaticArtists.TEMP_ARTIST)])
        response = self.client.get(reverse("findshows:view_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 403)

        self.login_static_user(self.StaticUsers.TEMP_ARTIST)
        response = self.client.get(reverse("findshows:view_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        response = self.client.get(reverse("findshows:view_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 403)



class MyConcertListTests(ConcertViewTestHelpers):
    def test_not_logged_in_my_concert_list_redirects(self):
        self.assert_redirects_to_login(reverse("findshows:my_concert_list"))


    def test_not_artist_user_my_concert_list_redirects(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        self.assert_redirects_to_login(reverse("findshows:my_concert_list"))


    def test_only_shows_users_artists(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist2 = self.get_static_instance(self.StaticArtists.NONLOCAL_ARTIST)
        concert1 = self.create_concert(artists=[self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)])
        concert2 = self.create_concert(artists=[artist2])

        response = self.client.get(reverse("findshows:my_concert_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/concert_list_for_artist.html')
        self.assertEqual(response.context['concerts'], [concert1])


    def test_date_filtering_and_sorting(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist1 = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        concert1 = self.create_concert(artists=[artist1], date=timezone_today() - datetime.timedelta(1))
        concert2 = self.create_concert(artists=[artist1], date=timezone_today())
        concert3 = self.create_concert(artists=[artist1], date=timezone_today() + datetime.timedelta(1))

        response = self.client.get(reverse("findshows:my_concert_list"))
        self.assertEqual(response.context['concerts'], [concert2, concert3])


    def test_create_link_shows_for_local_artists(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:my_concert_list"))
        self.assertIn(reverse('findshows:create_concert'), str(response.content))


    def test_create_link_doesnt_show_for_nonlocal_artist(self):
        self.login_static_user(self.StaticUsers.NONLOCAL_ARTIST)
        response = self.client.get(reverse("findshows:my_concert_list"))
        self.assertNotIn(reverse('findshows:create_concert'), str(response.content))


class RecordsCreatedTodayTests(ConcertViewTestHelpers):
    def test_venues_created_today(self):
        user_profile_1 = self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)
        user_profile_2 = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        self.create_venue(created_by=user_profile_1, created_at=timezone_today())
        self.create_venue(created_by=user_profile_1, created_at=timezone_today())
        self.create_venue(created_by=user_profile_2, created_at=timezone_today())
        self.create_venue(created_by=user_profile_1, created_at=timezone_today()+datetime.timedelta(1))
        self.create_venue(created_by=user_profile_1, created_at=timezone_today()-datetime.timedelta(1))
        self.assertEqual(records_created_today(Venue, user_profile_1), 2)
        self.assertEqual(records_created_today(Venue, user_profile_2), 1)

    def test_concerts_created_today(self):
        user_profile_1 = self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)
        user_profile_2 = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        self.create_concert(created_by=user_profile_1, created_at=timezone_today())
        self.create_concert(created_by=user_profile_1, created_at=timezone_today())
        self.create_concert(created_by=user_profile_2, created_at=timezone_today())
        self.create_concert(created_by=user_profile_1, created_at=timezone_today()+datetime.timedelta(1))
        self.create_concert(created_by=user_profile_1, created_at=timezone_today()-datetime.timedelta(1))
        self.assertEqual(records_created_today(Concert, user_profile_1), 2)
        self.assertEqual(records_created_today(Concert, user_profile_2), 1)


class CreateConcertTests(ConcertViewTestHelpers):
    """Tests edit_concert, but just the pathways that create a new concert.
    (i.e. the create_concert url)"""

    def test_not_logged_in_create_new_concert_redirects(self):
        self.assert_redirects_to_login(reverse("findshows:create_concert"))


    def test_not_artist_user_create_new_concert_redirects(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        self.assert_redirects_to_login(reverse("findshows:create_concert"))


    def test_non_local_artist_user_create_new_concert_redirects(self):
        self.login_static_user(self.StaticUsers.NONLOCAL_ARTIST)
        self.assert_redirects_to_login(reverse("findshows:create_concert"))


    def test_artist_user_can_create_new_concert(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:create_concert"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_concert.html')
        self.assert_blank_form(response.context['form'], ConcertForm)


    def test_user_doesnt_own_one_of_the_artists(self):
        artist = self.get_static_instance(self.StaticArtists.NONLOCAL_ARTIST)
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST) # different artist
        response = self.client.post(reverse("findshows:create_concert"), data=self.concert_post_request(artist))
        self.assertEqual(response.context['form'].errors["bill"][0][:17], "You may only post")


    def test_user_only_owns_nonlocal_artist(self):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist2 = self.get_static_instance(self.StaticArtists.NONLOCAL_ARTIST)
        user_profile.managed_artists.add(artist2)
        response = self.client.post(reverse("findshows:create_concert"), data=self.concert_post_request(artist2))
        self.assertEqual(response.context['form'].errors["bill"][0][:17], "You may only post")


    def test_concert_creation_limit(self):
        """Make sure we can create the max number of concerts but no more"""
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        for i in range(settings.MAX_DAILY_CONCERT_CREATES - 1):
            self.create_concert(created_by=user_profile)

        response = self.client.get(reverse("findshows:create_concert"))
        self.assertTemplateNotUsed(response, 'findshows/pages/cant_create_concert.html')
        self.assertTemplateUsed(response, 'findshows/pages/edit_concert.html')

        self.create_concert(created_by=user_profile)
        response = self.client.get(reverse("findshows:create_concert"))
        self.assertTemplateUsed(response, 'findshows/pages/cant_create_concert.html')
        self.assertTemplateNotUsed(response, 'findshows/pages/edit_concert.html')


    def test_concert_creation_limit_POST(self):
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)

        for i in range(settings.MAX_DAILY_CONCERT_CREATES):
            self.create_concert(created_by=user_profile)

        response = self.client.post(reverse("findshows:create_concert"), data=self.concert_post_request(artist))
        self.assertTemplateUsed(response, 'findshows/pages/cant_create_concert.html')
        self.assertTemplateNotUsed(response, 'findshows/pages/edit_concert.html')
        self.assert_records_created(Concert, settings.MAX_DAILY_CONCERT_CREATES)


    def test_create_concert_successful_POST(self):
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        self.assert_records_created(Concert, 0)
        response = self.client.post(reverse("findshows:create_concert"), data=self.concert_post_request(artist))
        self.assertRedirects(response, reverse('findshows:my_concert_list'))
        concerts = Concert.objects.all()
        self.assertEqual(len(concerts), 1)
        self.assertEqual(concerts[0].created_by, user_profile)
        self.assertEqual(concerts[0].created_at, timezone_today())


class EditConcertTests(ConcertViewTestHelpers):
    """Tests edit_concert, but just the pathways that edit an existing concert.
    (i.e. the edit_concert url)"""

    def test_edit_concert_doesnt_exist_GET(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:edit_concert", args=(100,)))
        self.assertEqual(response.status_code, 404)


    def test_edit_concert_doesnt_exist_POST(self):
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.post(reverse("findshows:edit_concert", args=(100,)), data=self.concert_post_request(artist))
        self.assertEqual(response.status_code, 404)


    def test_user_doesnt_own_concert_GET(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        user_profile_2 = self.create_user_profile()
        concert = self.create_concert(created_by=user_profile_2)

        response = self.client.get(reverse("findshows:edit_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 403)


    def test_user_doesnt_own_concert_POST(self):
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        user2 = self.create_user_profile()
        concert_before = self.create_concert(created_by=user2)

        response = self.client.post(reverse("findshows:edit_concert", args=(concert_before.pk,)), data=self.concert_post_request(artist))
        self.assertEqual(response.status_code, 403)

        concert_after = Concert.objects.get(pk=concert_before.pk)
        self.assertEqual(concert_before, concert_after)


    def test_edit_concert_successful_GET(self):
        user = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        concert = self.create_concert(created_by=user)
        response = self.client.get(reverse("findshows:edit_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_concert.html')
        self.assertEqual(response.context['form'].instance, concert)


    def test_edit_concert_successful_POST(self):
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        user = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        concert_before = self.create_concert(created_by=user, artists=[artist])

        response = self.client.post(reverse("findshows:edit_concert", args=(concert_before.pk,)), data=self.concert_post_request(artist))
        self.assertRedirects(response, reverse('findshows:my_concert_list'))

        concert_after = Concert.objects.get(pk=concert_before.pk)
        self.assertEqual(concert_after.ticket_link, 'https://www.thisisthevalueforconcertpostrequests.com')
