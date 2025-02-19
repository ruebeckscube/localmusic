

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


    def test_date_is_in_future(self):
        form = ShowFinderForm(form_data(timezone_today() - timedelta(1)))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['date'], ["Date is in the past. Please select a valid date."])


    def test_end_date_doesnt_error_when_daterange_false(self):
        form = ShowFinderForm(form_data(timezone_today(), timezone_today()-timedelta(1)))
        self.assertTrue(form.is_valid())


class DateRangeValidationTests(TestCase):
    def test_range_missing_end_date(self):
        data = form_data(is_date_range=True)
        del data['end_date']
        form = ShowFinderForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['end_date'], ["Please enter an end date, or hide date range."])


    def test_range_end_date_in_past(self):
        form = ShowFinderForm(form_data(timezone_today()-timedelta(2), timezone_today()-timedelta(1), True))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['end_date'], ["End date is in the past. Please select a valid date."])


    def test_range_end_date_before_start_date(self):
        form = ShowFinderForm(form_data(timezone_today()+timedelta(2), timezone_today(), True))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['__all__'], ["Please enter a date range with the end date after the start date."])


    def test_range_max_date_range(self):
        form = ShowFinderForm(form_data(timezone_today(), timezone_today()+timedelta(settings.MAX_DATE_RANGE + 1), True))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['__all__'], ["Max date range is " + str(settings.MAX_DATE_RANGE) + " days."])
