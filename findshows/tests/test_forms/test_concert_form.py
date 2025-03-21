import datetime
import json
from django.views.generic.dates import timezone_today
from findshows.forms import ConcertForm

from findshows.tests.test_helpers import TestCaseHelpers


class ConcertFormTestHelpers(TestCaseHelpers):
    def form_data(self,
                  date=None,
                  venue=None,
                  artists=None,
                  ticket_description="10 buckaroos",
                  tags=None):
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
            'venue': str((venue or self.create_venue()).pk),
            'bill': self.bill_json_from_artist_list(artists or [self.create_artist(f"Test Artist {i}") for i in range(3)]),
            'ticket_link': 'https://www.testurl.com',
            'ticket_description': ticket_description,
            'tags': tags or ['OG']
        }

    def file_data(self):
        return {
            'poster': self.image_file(),
        }

    def bill_json_from_artist_list(self, artists):
        return json.dumps([{'id': a.id, 'name': a.name} for a in artists])


class InitTests(ConcertFormTestHelpers):
    def test_from_instance(self):
        artist1 = self.create_artist('chris')
        artist2 = self.create_artist('dave')
        artist3 = self.create_artist('bruebeck')
        concert = self.create_concert(artists=[artist2, artist1, artist3])
        form = ConcertForm(instance=concert)
        self.assertEqual(form['bill'].value(), self.bill_json_from_artist_list([artist2, artist1, artist3]))

    def test_new(self):
        form = ConcertForm()
        self.assertEqual(form['bill'].value(), json.dumps([]))


class ValidationTests(ConcertFormTestHelpers):
    # We test whether the bill includes an artist of the editing user
    # in test_concert_views because it relies on the form being called correctly

    def test_unique_venue_and_date(self):
        venue = self.create_venue()
        tomorrow = timezone_today() + datetime.timedelta(1)
        self.create_concert(date=tomorrow, venue=venue)
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        user_profile = self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)
        form = ConcertForm(self.form_data(date=tomorrow, venue=venue, artists=[artist]),
                           self.file_data())
        form.set_editing_user(user_profile.user)
        self.assertFalse(form.is_valid())
        trunc_msg = "There is already a show"
        self.assertEqual(form.errors.as_data()['__all__'][0].message[:len(trunc_msg)], trunc_msg)
