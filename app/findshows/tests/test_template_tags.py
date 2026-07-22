from datetime import date
from unittest.mock import patch

from django.test import override_settings

from findshows.templatetags.findshows_tags import announce_date, share_date
from findshows.tests.test_helpers import TestCaseHelpers

TODAY = date(2026, 5, 6) # Wed May 6 2026

def _format_date(y, m, d):
    if y and m and d:
        return date(y, m, d).strftime("%b %d")
    else:
        return "n/a"

@override_settings(WEEKLY_EMAIL_DAY=6) # Sunday for consistent testing
@patch('findshows.templatetags.findshows_tags.timezone_today', return_value=TODAY)
class ConcertShareDateTests(TestCaseHelpers):
    def assert_result(self, result_text, expected_text, y, m, d):
        self.assertIn(expected_text, result_text)
        self.assertIn(_format_date(y, m, d), result_text)

    def test_concert_already_shared(self, *_):
        concert = self.create_concert(date=TODAY, shared=date(2026, 4, 2))
        self.assert_result(share_date(concert), "Shared", 2026, 4, 2)

    def test_concert_day_of_shares(self, *_):
        concert = self.create_concert(date=date(2026, 6, 7)) # Sun Jun 7
        self.assert_result(share_date(concert), "To share", 2026, 6, 7)

    def test_concert_day_before_shares(self, *_):
        concert = self.create_concert(date=date(2026, 6, 13)) # Sat Jun 13
        self.assert_result(share_date(concert), "To share", 2026, 6, 7)

    def test_cancelled_concert_not_shared(self, *_):
        concert = self.create_concert(date=date(2026, 6, 13), cancelled=True) # Sat Jun 13
        self.assert_result(share_date(concert), "Shared", None, None, None)

    def test_concert_too_late_to_share(self, *_):
        concert = self.create_concert(date=date(2026, 5, 8))
        self.assert_result(share_date(concert), "Shared", None, None, None)

    def test_concert_day_of_today_not_shared(self, mock_today):
        mock_today.return_value=date(2026, 5, 10) # Sun May 10
        concert = self.create_concert(date=date(2026, 5, 10))
        self.assert_result(share_date(concert), "Shared", None, None, None)


    def test_concert_already_announced(self, *_):
        concert = self.create_concert(date=TODAY, announced=date(2026, 4, 3))
        self.assert_result(announce_date(concert), "Announced", 2026, 4, 3)

    def test_concert_announces(self, *_):
        concert = self.create_concert(date=date(2026, 6, 7)) # Sun Jun 7
        self.assert_result(announce_date(concert), "To announce", 2026, 5, 10) # Sun May 10

    def test_concert_day_before_cutoff_not_announced(self, *_):
        # Because it's shared this week instead
        concert = self.create_concert(date=date(2026, 5, 16)) # Sat May 16
        self.assert_result(announce_date(concert), "Announced", None, None, None)

    def test_concert_day_after_cutoff_announces(self, *_):
        concert = self.create_concert(date=date(2026, 5, 17)) # Sun May 17
        self.assert_result(announce_date(concert), "To announce", 2026, 5, 10) # Sun May 10

    def test_cancelled_concert_not_announced(self, *_):
        concert = self.create_concert(date=date(2026, 6, 13), cancelled=True) # Sat Jun 13
        self.assert_result(announce_date(concert), "Announced", None, None, None)

    def test_concert_day_of_today_not_announced(self, mock_today):
        mock_today.return_value=date(2026, 5, 10) # Sun May 10
        concert = self.create_concert(date=date(2026, 5, 17)) # Sun May 17
        self.assert_result(announce_date(concert), "Announced", None, None, None)
