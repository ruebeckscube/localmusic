

from datetime import timedelta
from django.conf import settings
from django.test import TestCase
from django.utils.datastructures import MultiValueDict
from django.views.generic.dates import timezone_today

from findshows.forms import ShowFinderForm


def form_data(date=None, end_date=None, is_date_range=False):
    return MultiValueDict({
        'date': [date or timezone_today()],
        'end_date': [end_date or timezone_today()],
        'is_date_range': [is_date_range]
    })


class SingleDateValidationTests(TestCase):
    def test_valid(self):
        form = ShowFinderForm(form_data(timezone_today()))
        self.assertTrue(form.is_valid())


    def test_date_is_in_past(self):
        form = ShowFinderForm(form_data(timezone_today() - timedelta(1)))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['date'], timezone_today())


    def test_end_date_doesnt_error_when_daterange_false(self):
        form = ShowFinderForm(form_data(timezone_today(), timezone_today()-timedelta(1)))
        self.assertTrue(form.is_valid())


class DateRangeValidationTests(TestCase):
    def test_range_missing_end_date(self):
        data = form_data(is_date_range=True)
        del data['end_date']
        form = ShowFinderForm(data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['end_date'], timezone_today())


    def test_range_both_in_past(self):
        form = ShowFinderForm(form_data(timezone_today()-timedelta(2), timezone_today()-timedelta(1), True))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['date'], timezone_today())
        self.assertEqual(form.cleaned_data['end_date'], timezone_today())


    def test_range_end_date_before_start_date(self):
        tomorrowmorrow = timezone_today() + timedelta(2)
        form = ShowFinderForm(form_data(tomorrowmorrow, timezone_today(), True))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['end_date'], tomorrowmorrow)


    def test_range_max_date_range(self):
        form = ShowFinderForm(form_data(timezone_today(), timezone_today()+timedelta(settings.MAX_DATE_RANGE + 1), True))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['__all__'], ["Max date range is " + str(settings.MAX_DATE_RANGE) + " days."])
