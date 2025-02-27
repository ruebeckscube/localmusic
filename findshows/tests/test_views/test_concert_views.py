import datetime
import json

from django.conf import settings
from django.urls import reverse
from django.views.generic.dates import timezone_today
from findshows.forms import ConcertForm

from findshows.models import Concert, Venue
from findshows.tests.test_helpers import TestCaseHelpers, TestCaseHelpers, create_artist_t, create_concert_t, create_user_profile_t, create_venue_t, image_file_t
from findshows.views import records_created_today


def concert_post_request(venue, artist):
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
            'venue': [str(venue.pk)],
            'ticket_link': ['https://www.testurl.com'],
            'ticket_description': ['$10 suggested'],
            'poster': image_file_t(),
            'bill': json.dumps([{"id":artist.pk,"name":artist.name}]),
            'tags': ['OG']
            }

class ViewConcertTests(TestCaseHelpers):
    def test_concert_exists(self):
        concert = create_concert_t()
        response = self.client.get(reverse("findshows:view_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/view_concert.html')
        self.assertEqual(response.context["concert"], concert)

    def test_concert_doesnt_exist(self):
        response = self.client.get(reverse("findshows:view_concert", args=(1,)))
        self.assertEqual(response.status_code, 404)


class MyConcertListTests(TestCaseHelpers):
    def test_not_logged_in_my_concert_list_redirects(self):
        self.assert_redirects_to_login(reverse("findshows:my_concert_list"))


    def test_not_artist_user_my_concert_list_redirects(self):
        self.create_and_login_non_artist_user()
        self.assert_redirects_to_login(reverse("findshows:my_concert_list"))


    def test_only_shows_users_artists(self):
        artist1 = create_artist_t()
        artist2 = create_artist_t()
        concert1 = create_concert_t(artists=[artist1])
        concert2 = create_concert_t(artists=[artist2])
        user = self.create_and_login_artist_user(artist1)

        response = self.client.get(reverse("findshows:my_concert_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/concert_list_for_artist.html')
        self.assertEqual(response.context['concerts'], [concert1])


    def test_date_filtering_and_sorting(self):
        artist1 = create_artist_t()
        concert1 = create_concert_t(artists=[artist1], date=timezone_today() - datetime.timedelta(1))
        concert2 = create_concert_t(artists=[artist1], date=timezone_today())
        concert3 = create_concert_t(artists=[artist1], date=timezone_today() + datetime.timedelta(1))
        self.create_and_login_artist_user(artist1)

        response = self.client.get(reverse("findshows:my_concert_list"))
        self.assertEqual(response.context['concerts'], [concert2, concert3])


    def test_create_link_shows_for_local_artists(self):
        artist = create_artist_t(local=True)
        self.create_and_login_artist_user(artist)

        response = self.client.get(reverse("findshows:my_concert_list"))
        self.assertIn(reverse('findshows:create_concert'), str(response.content))


    def test_create_link_doesnt_show_for_nonlocal_artist(self):
        artist = create_artist_t(local=False)
        self.create_and_login_artist_user(artist)

        response = self.client.get(reverse("findshows:my_concert_list"))
        self.assertNotIn(reverse('findshows:create_concert'), str(response.content))


class RecordsCreatedTodayTests(TestCaseHelpers):
    def test_venues_created_today(self):
        user1 = create_user_profile_t()
        user2 = create_user_profile_t()
        create_venue_t(created_by=user1, created_at=timezone_today())
        create_venue_t(created_by=user1, created_at=timezone_today())
        create_venue_t(created_by=user2, created_at=timezone_today())
        create_venue_t(created_by=user1, created_at=timezone_today()+datetime.timedelta(1))
        create_venue_t(created_by=user1, created_at=timezone_today()-datetime.timedelta(1))
        self.assertEqual(records_created_today(Venue, user1), 2)
        self.assertEqual(records_created_today(Venue, user2), 1)

    def test_concerts_created_today(self):
        user1 = create_user_profile_t()
        user2 = create_user_profile_t()
        create_concert_t(created_by=user1, created_at=timezone_today())
        create_concert_t(created_by=user1, created_at=timezone_today())
        create_concert_t(created_by=user2, created_at=timezone_today())
        create_concert_t(created_by=user1, created_at=timezone_today()+datetime.timedelta(1))
        create_concert_t(created_by=user1, created_at=timezone_today()-datetime.timedelta(1))
        self.assertEqual(records_created_today(Concert, user1), 2)
        self.assertEqual(records_created_today(Concert, user2), 1)


class CreateConcertTests(TestCaseHelpers):
    """Tests edit_concert, but just the pathways that create a new concert.
    (i.e. the create_concert url)"""

    def test_not_logged_in_create_new_concert_redirects(self):
        self.assert_redirects_to_login(reverse("findshows:create_concert"))


    def test_not_artist_user_create_new_concert_redirects(self):
        self.create_and_login_non_artist_user()
        self.assert_redirects_to_login(reverse("findshows:create_concert"))


    def test_non_local_artist_user_create_new_concert_redirects(self):
        artist = create_artist_t(local=False)
        self.create_and_login_artist_user(artist)
        self.assert_redirects_to_login(reverse("findshows:create_concert"))


    def test_artist_user_can_create_new_concert(self):
        self.create_and_login_artist_user()
        response = self.client.get(reverse("findshows:create_concert"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_concert.html')
        self.assert_blank_form(response.context['form'], ConcertForm)


    def test_user_doesnt_own_one_of_the_artists(self):
        artist = create_artist_t()
        venue = create_venue_t()
        user = self.create_and_login_artist_user() # different artist
        response = self.client.post(reverse("findshows:create_concert"), data=concert_post_request(venue, artist))
        self.assertEqual(response.context['form'].errors["bill"][0][:17], "You may only post")


    def test_user_only_owns_nonlocal_artist(self):
        artist1 = create_artist_t(local=True)
        artist2 = create_artist_t(local=False)
        venue = create_venue_t()
        user = self.create_and_login_artist_user(artist1)
        user.managed_artists.add(artist2)
        user.save()
        response = self.client.post(reverse("findshows:create_concert"), data=concert_post_request(venue, artist2))
        self.assertEqual(response.context['form'].errors["bill"][0][:17], "You may only post")


    def test_concert_creation_limit(self):
        """Make sure we can create the max number of concerts but no more"""
        user = self.create_and_login_artist_user()
        for i in range(settings.MAX_DAILY_CONCERT_CREATES - 1):
            create_concert_t(created_by=user)

        response = self.client.get(reverse("findshows:create_concert"))
        self.assertTemplateNotUsed(response, 'findshows/pages/cant_create_concert.html')
        self.assertTemplateUsed(response, 'findshows/pages/edit_concert.html')

        create_concert_t(created_by=user)
        response = self.client.get(reverse("findshows:create_concert"))
        self.assertTemplateUsed(response, 'findshows/pages/cant_create_concert.html')
        self.assertTemplateNotUsed(response, 'findshows/pages/edit_concert.html')


    def test_concert_creation_limit_POST(self):
        artist = create_artist_t()
        venue = create_venue_t()
        user = self.create_and_login_artist_user(artist)

        for i in range(settings.MAX_DAILY_CONCERT_CREATES):
            create_concert_t(created_by=user)

        response = self.client.post(reverse("findshows:create_concert"), data=concert_post_request(venue, artist))
        self.assertTemplateUsed(response, 'findshows/pages/cant_create_concert.html')
        self.assertTemplateNotUsed(response, 'findshows/pages/edit_concert.html')
        self.assert_records_created(Concert, settings.MAX_DAILY_CONCERT_CREATES)


    def test_create_concert_successful_POST(self):
        artist = create_artist_t()
        venue = create_venue_t()
        user = self.create_and_login_artist_user(artist)
        self.assert_records_created(Concert, 0)
        response = self.client.post(reverse("findshows:create_concert"), data=concert_post_request(venue, artist))
        self.assertRedirects(response, reverse('findshows:my_concert_list'))
        concerts = Concert.objects.all()
        self.assertEqual(len(concerts), 1)
        self.assertEqual(concerts[0].created_by, user)
        self.assertEqual(concerts[0].created_at, timezone_today())


class EditConcertTests(TestCaseHelpers):
    """Tests edit_concert, but just the pathways that edit an existing concert.
    (i.e. the edit_concert url)"""

    def test_edit_concert_doesnt_exist_GET(self):
        self.create_and_login_artist_user()
        response = self.client.get(reverse("findshows:edit_concert", args=(3,)))
        self.assertEqual(response.status_code, 404)


    def test_edit_concert_doesnt_exist_POST(self):
        artist = create_artist_t()
        venue = create_venue_t()
        self.create_and_login_artist_user(artist)
        response = self.client.post(reverse("findshows:edit_concert", args=(3,)), data=concert_post_request(venue, artist))
        self.assertEqual(response.status_code, 404)


    def test_user_doesnt_own_concert_GET(self):
        user1 = self.create_and_login_artist_user()
        user2 = create_user_profile_t()
        concert = create_concert_t(created_by=user2)

        response = self.client.get(reverse("findshows:edit_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 403)


    def test_user_doesnt_own_concert_POST(self):
        venue = create_venue_t()
        artist = create_artist_t()
        user1 = self.create_and_login_artist_user(artist)
        user2 = create_user_profile_t()
        concert_before = create_concert_t(created_by=user2)

        response = self.client.post(reverse("findshows:edit_concert", args=(concert_before.pk,)), data=concert_post_request(venue, artist))
        self.assertEqual(response.status_code, 403)

        concert_after = Concert.objects.get(pk=concert_before.pk)
        self.assertEqual(concert_before, concert_after)


    def test_edit_concert_successful_GET(self):
        user = self.create_and_login_artist_user()
        concert = create_concert_t(created_by=user)
        response = self.client.get(reverse("findshows:edit_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_concert.html')
        self.assertEqual(response.context['form'].instance, concert)


    def test_edit_concert_successful_POST(self):
        venue1 = create_venue_t()
        venue2 = create_venue_t()
        artist = create_artist_t()
        user = self.create_and_login_artist_user(artist)
        concert_before = create_concert_t(created_by=user, artists=[artist], venue=venue1)

        response = self.client.post(reverse("findshows:edit_concert", args=(concert_before.pk,)), data=concert_post_request(venue2, artist))
        self.assertRedirects(response, reverse('findshows:my_concert_list'))

        concert_after = Concert.objects.get(pk=concert_before.pk)
        self.assertEqual(concert_after.venue, venue2)
