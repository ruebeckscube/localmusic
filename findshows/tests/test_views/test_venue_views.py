import json
from django.conf import settings
from django.urls import reverse
from django.views.generic.dates import timezone_today
from findshows.forms import VenueForm
from findshows.models import Venue

from findshows.tests.test_helpers import TestCaseHelpers, create_artist_t, create_venue_t


class VenueSearchTests(TestCaseHelpers):
    def test_handles_missing_params(self):
        response = self.client.get(reverse("findshows:venue_search_results"))
        self.assertEqual(response.content, b'')

    def test_search(self):
        bottle = create_venue_t(name="Empty Bottle")
        thalia = create_venue_t(name="Thalia Hall")
        lincoln = create_venue_t(name="Lincoln Hall")

        query = 'hall'
        response = self.client.get(reverse("findshows:venue_search_results"),
                                   data={'venue-search': query})
        self.assert_equal_as_sets(response.context['venues'], [thalia, lincoln])

        query = 'bot'
        response = self.client.get(reverse("findshows:venue_search_results"),
                                   data={'venue-search': query})
        self.assert_equal_as_sets(response.context['venues'], [bottle])



def venue_post_data():
    return {'venue-name': 'Gallery Cabaret',
            'venue-address': ['anetseonahoeint'],
            'venue-ages': ['17'],
            'venue-website': ['asoeth.com']}


class CreateVenueTests(TestCaseHelpers):
    def test_get_doesnt_create(self):
        self.create_and_login_artist_user()
        self.client.get(reverse("findshows:create_venue"))
        self.assertEqual(Venue.objects.all().count(), 0)


    def test_not_logged_in_doesnt_create(self):
        self.client.post(reverse("findshows:create_venue"), data=venue_post_data())
        self.assertEqual(Venue.objects.all().count(), 0)


    def test_not_artist_user_doesnt_create(self):
        self.create_and_login_non_artist_user()
        self.client.post(reverse("findshows:create_venue"), data=venue_post_data())
        self.assertEqual(Venue.objects.all().count(), 0)


    def test_not_local_artist_user_doesnt_create(self):
        artist = create_artist_t(local=False)
        self.create_and_login_artist_user(artist)
        self.client.post(reverse("findshows:create_venue"), data=venue_post_data())
        self.assertEqual(Venue.objects.all().count(), 0)


    def test_successful_create(self):
        user = self.create_and_login_artist_user()
        response = self.client.post(reverse("findshows:create_venue"), data=venue_post_data())
        self.assert_blank_form(response.context['venue_form'], VenueForm)

        venues = Venue.objects.all()
        self.assertEqual(len(venues), 1)
        self.assertEqual(venues[0].created_by, user)
        self.assertEqual(venues[0].created_at, timezone_today())

        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertTrue('successfully-created-venue' in hx_trigger)


    def test_invalid_form(self):
        self.create_and_login_artist_user()
        data=venue_post_data()
        data['venue-name'] = ''
        response = self.client.post(reverse("findshows:create_venue"), data)
        self.assert_not_blank_form(response.context['venue_form'], VenueForm)
        self.assert_records_created(Venue, 0)

        self.assertFalse('HX-Trigger' in response.headers)


    def test_daily_limit(self):
        user = self.create_and_login_artist_user()

        for i in range(settings.MAX_DAILY_VENUE_CREATES):
            create_venue_t(created_by=user)

        response = self.client.post(reverse("findshows:create_venue"), data=venue_post_data())
        self.assertTemplateUsed(response, 'findshows/htmx/cant_create_venue.html')
        self.assertTemplateNotUsed(response, 'findshows/htmx/venue_form.html')
        self.assert_records_created(Venue, settings.MAX_DAILY_VENUE_CREATES)
