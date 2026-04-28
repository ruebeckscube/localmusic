import datetime
import json
from django.conf import settings
from django.views.generic.dates import timezone_today
from findshows.forms import ConcertForm

from findshows.tests.test_helpers import TestCaseHelpers


class ConcertFormTestHelpers(TestCaseHelpers):
    def make_form(self,
                  date=None,
                  venue=None,
                  artists=list(),
                  ticket_description="10 buckaroos",
                  tags=None,
                  user_profile = None,
                  doors_time = None,
                  start_time = None,
                  ):
        if not user_profile:
            user_profile = self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)
            artists.append(self.get_static_instance(self.StaticArtists.LOCAL_ARTIST))
        data = {
            'date': date or timezone_today(),
            'doors_time': doors_time if doors_time is not None else '20:30',
            'start_time': start_time if start_time is not None else '21:00',
            'end_time': '23:00',
            'venue': str((venue or self.create_venue()).pk),
            'bill': self.bill_json_from_artist_list(artists or [self.create_artist(f"Test Artist {i}") for i in range(3)]),
            'ticket_link': 'https://www.testurl.com',
            'ticket_description': ticket_description,
            'tags': tags or ['OG']
        }
        form = ConcertForm(data, {'poster': self.image_file()})
        form.set_editing_user(user_profile.user)
        return form

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
    def test_valid(self):
        # This is to make sure our form_data helper is valid and not giving false negatives/positives elsewhere
        form = self.make_form()
        self.assertTrue(form.is_valid())

    def test_unique_venue_and_date(self):
        venue = self.create_venue()
        tomorrow = timezone_today() + datetime.timedelta(1)
        self.create_concert(date=tomorrow, venue=venue)
        form = self.make_form(date=tomorrow, venue=venue)
        self.assertFalse(form.is_valid())
        self.assertIn("There is already a show", form.errors['__all__'][0])


    def test_venue_declined_listing(self):
        venue = self.create_venue(declined_listing=True)
        form = self.make_form(venue=venue)
        self.assertFalse(form.is_valid())
        self.assertIn("declined listings",
                      str(form.errors['venue'][0]))


    def test_date_too_far_future(self):
        date = timezone_today() + datetime.timedelta(settings.MAX_FUTURE_CONCERT_WEEKS * 7 + 3)
        form = self.make_form(date=date)
        self.assertFalse(form.is_valid())
        self.assertIn("Date cannot be more than", form.errors['date'][0])


    def test_start_time_before_doors(self):
        form = self.make_form(doors_time='20:00', start_time='19:00')
        self.assertFalse(form.is_valid())
        self.assertIn("Doors time must be before", form.errors['__all__'][0])

        form = self.make_form(doors_time='', start_time='19:00') # check optional doors time doesn't throw error
        self.assertTrue(form.is_valid())
