import datetime
import json
from django.views.generic.dates import timezone_today
from findshows.forms import ConcertForm
from findshows.models import Concert

from findshows.tests.test_helpers import TestCaseHelpers, create_artist_t, create_concert_t, create_user_profile_t, create_venue_t, image_file_t

def form_data(date=None,
              venue=None,
              artists=None,
              ticket_description="10 buckaroos",
              tags=None) -> Concert:
    return {
        'date': date or timezone_today(),
        'doors_time_hour': '8',
        'doors_time_minutes': '00',
        'doors_time_ampm': 'pm',
        'start_time_hour': '8',
        'start_time_minutes': '30',
        'start_time_ampm': 'pm',
        'end_time_hour': '11',
        'end_time_minutes': '30',
        'end_time_ampm': 'pm',
        'venue': str((venue or create_venue_t()).pk),
        'bill': bill_json_from_artist_list(artists or [create_artist_t(f"Test Artist {i}") for i in range(3)]),
        'ticket_link': 'https://www.testurl.com',
        'ticket_description': ticket_description,
        'tags': tags or ['OG']
    }

def file_data():
    return {
        'poster': image_file_t(),
    }

def bill_json_from_artist_list(artists):
    return json.dumps([{'id': a.id, 'name': a.name} for a in artists])


class InitTests(TestCaseHelpers):
    def test_from_instance(self):
        artist1 = create_artist_t('chris')
        artist2 = create_artist_t('dave')
        artist3 = create_artist_t('bruebeck')
        concert = create_concert_t(artists=[artist2, artist1, artist3])
        form = ConcertForm(instance=concert)
        self.assertEqual(form['bill'].value(), bill_json_from_artist_list([artist2, artist1, artist3]))

    def test_new(self):
        form = ConcertForm()
        self.assertEqual(form['bill'].value(), json.dumps([]))


class ValidationTests(TestCaseHelpers):
    # We test whether the bill includes an artist of the editing user
    # in test_concert_views because it relies on the form being called correctly

    def test_unique_venue_and_date(self):
        venue = create_venue_t()
        tomorrow = timezone_today() + datetime.timedelta(1)
        create_concert_t(date=tomorrow, venue=venue)
        artist = create_artist_t()
        user_profile = create_user_profile_t()
        user_profile.managed_artists.add(artist)
        form = ConcertForm(form_data(date=tomorrow, venue=venue, artists=[artist]),
                           file_data())
        form.set_editing_user(user_profile.user)
        self.assertFalse(form.is_valid())
        trunc_msg = "There is already a show"
        self.assertEqual(form.errors.as_data()['__all__'][0].message[:len(trunc_msg)], trunc_msg)
