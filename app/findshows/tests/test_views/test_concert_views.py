import datetime
import json

from django.conf import settings
from django.urls import reverse
from django.views.generic.dates import timezone_today
from findshows.forms import ConcertForm

from findshows.models import ArtistVerificationStatus, Concert, Venue
from findshows.tests.test_helpers import TestCaseHelpers


class ConcertViewTestHelpers(TestCaseHelpers):
    def concert_post_request(self, artist):
        return {'date': (timezone_today() + datetime.timedelta(3)).isoformat(),
                'doors_time': ['20:00'],
                'start_time': ['20:30'],
                'end_time': ['23:30'],
                'venue': [str(self.StaticVenues.DEFAULT_VENUE.value)],
                'ticket_link': ['https://www.thisisthevalueforconcertpostrequests.com'],
                'ticket_description': ['$10 suggested'],
                'poster': self.image_file(),
                'bill': json.dumps([{"id":artist.pk,"name":artist.name}]),
                'tags': ['OG']
                }


class ViewConcertTests(ConcertViewTestHelpers):
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


    def test_concert_made_by_unverified_user_is_only_viewable_by_artists_on_bill(self):
        unverified_user = self.create_user_profile(artist_verification_status=ArtistVerificationStatus.UNVERIFIED)
        artist = self.create_artist(created_by=unverified_user)
        unverified_user.managed_artists.add(artist)
        concert = self.create_concert(artists=[self.get_static_instance(self.StaticArtists.LOCAL_ARTIST),
                                               artist],
                                      created_by=unverified_user)
        response = self.client.get(reverse("findshows:view_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 403)

        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:view_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        self.login_static_user(self.StaticUsers.TEMP_ARTIST)
        response = self.client.get(reverse("findshows:view_concert", args=(concert.pk,)))
        self.assertEqual(response.status_code, 403)


    def test_visible_if_and_only_if_created_by_verified(self):
        visible_concerts = (self.create_concert(created_by=self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)),
                            self.create_concert(created_by=self.create_user_profile(artist_verification_status=ArtistVerificationStatus.INVITED)))
        hidden_concerts = (self.create_concert(created_by=self.get_static_instance(self.StaticUsers.NON_ARTIST)),
                           self.create_concert(created_by=self.create_user_profile(artist_verification_status=ArtistVerificationStatus.UNVERIFIED)),
                           self.create_concert(created_by=self.create_user_profile(artist_verification_status=ArtistVerificationStatus.DEVERIFIED)),
                           self.create_concert(created_by=self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)))

        for concert in visible_concerts:
            response = self.client.get(reverse("findshows:view_concert", args=(concert.pk,)))
            self.assertEqual(response.status_code, 200)
        for concert in hidden_concerts:
            response = self.client.get(reverse("findshows:view_concert", args=(concert.pk,)))
            self.assertEqual(response.status_code, 403)


class RecordsCreatedTodayTests(ConcertViewTestHelpers):
    def test_venues_created_today(self):
        user_profile_1 = self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)
        user_profile_2 = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        self.create_venue(created_by=user_profile_1, created_at=timezone_today())
        self.create_venue(created_by=user_profile_1, created_at=timezone_today())
        self.create_venue(created_by=user_profile_2, created_at=timezone_today())
        self.create_venue(created_by=user_profile_1, created_at=timezone_today()+datetime.timedelta(1))
        self.create_venue(created_by=user_profile_1, created_at=timezone_today()-datetime.timedelta(1))
        self.assertEqual(user_profile_1.records_created_today(Venue), 2)
        self.assertEqual(user_profile_2.records_created_today(Venue), 1)

    def test_concerts_created_today(self):
        user_profile_1 = self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)
        user_profile_2 = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        self.create_concert(created_by=user_profile_1, created_at=timezone_today())
        self.create_concert(created_by=user_profile_1, created_at=timezone_today())
        self.create_concert(created_by=user_profile_2, created_at=timezone_today())
        self.create_concert(created_by=user_profile_1, created_at=timezone_today()+datetime.timedelta(1))
        self.create_concert(created_by=user_profile_1, created_at=timezone_today()-datetime.timedelta(1))
        self.assertEqual(user_profile_1.records_created_today(Concert), 2)
        self.assertEqual(user_profile_2.records_created_today(Concert), 1)


class CreateConcertTests(ConcertViewTestHelpers):
    """Tests edit_concert, but just the pathways that create a new concert.
    (i.e. the create_concert url)"""
    def test_unverified_email_can_GET_but_not_POST(self):
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        user_profile.email_is_verified = False
        user_profile.save()

        response = self.client.get(reverse("findshows:create_concert"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_concert.html')
        self.assert_blank_form(response.context['form'], ConcertForm)

        response = self.client.post(reverse("findshows:create_concert"), data=self.concert_post_request(artist))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_concert.html')
        self.assertIn("Please verify your email before submitting.", response.context['form'].errors['__all__'])


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
        self.assertEqual(response.context['form'].errors["bill"][0][:17], "The bill must inc")


    def test_user_only_owns_nonlocal_artist(self):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist2 = self.get_static_instance(self.StaticArtists.NONLOCAL_ARTIST)
        user_profile.managed_artists.add(artist2)
        response = self.client.post(reverse("findshows:create_concert"), data=self.concert_post_request(artist2))
        self.assertEqual(response.context['form'].errors["bill"][0][:17], "The bill must inc")


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
        concerts = Concert.objects.all()
        self.assertEqual(len(concerts), 1)
        self.assertEqual(concerts[0].created_by, user_profile)
        self.assertEqual(concerts[0].created_at, timezone_today())
        self.assertRedirects(response, reverse('findshows:view_concert', args=(concerts[0].pk,)))


class EditConcertTests(ConcertViewTestHelpers):
    """Tests edit_concert, but just the pathways that edit an existing concert.
    (i.e. the edit_concert url)"""
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
        self.assertRedirects(response, reverse('findshows:view_concert', args=(concert_before.pk,)))

        concert_after = Concert.objects.get(pk=concert_before.pk)
        self.assertEqual(concert_after.ticket_link, 'https://www.thisisthevalueforconcertpostrequests.com')


class CancelConcertTests(TestCaseHelpers):
    def test_unverified_email_can_cancel(self):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        concert = self.create_concert(created_by=user_profile)
        user_profile.email_is_verified = False
        user_profile.save()

        self.client.post(reverse("findshows:cancel_concert", args=(concert.pk,)))
        concert.refresh_from_db()
        self.assertTrue(concert.cancelled)


    def test_cancel_concert(self):
        user = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        concert = self.create_concert(created_by=user)

        self.client.post(reverse("findshows:cancel_concert", args=(concert.pk,)))
        concert.refresh_from_db()
        self.assertTrue(concert.cancelled)


    def test_uncancel_concert(self):
        user = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        concert = self.create_concert(created_by=user, cancelled=True)

        self.client.post(reverse("findshows:uncancel_concert", args=(concert.pk,)))
        concert.refresh_from_db()
        self.assertFalse(concert.cancelled)


    def test_uncancel_concert_conflict(self):
        user = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        concert1 = self.create_concert(created_by=user, cancelled=True)
        concert2 = self.create_concert(created_by=user)

        response = self.client.post(reverse("findshows:uncancel_concert", args=(concert1.pk,)))
        concert1.refresh_from_db()
        self.assertTrue(concert1.cancelled)
        self.assertIn("there is another concert at this venue on this date", str(response.content))
