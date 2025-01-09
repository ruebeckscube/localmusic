from unittest.mock import patch

from django.test import TestCase
from django.core import mail
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from findshows.tests.test_helpers import TestCaseHelpers


def contact_post_request():
    return {
        'email': ['test@em.ail'],
        'subject': ['bad'],
        'message': ["wow this website sucks"],
        'type': ['oth']
    }


class ContactTests(TestCase):
    def test_contact_GET(self):
        response = self.client.get(reverse("findshows:contact"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


    def test_contact_POST_success(self):
        response = self.client.post(reverse("findshows:contact"), contact_post_request())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(response.context['form'].data, MultiValueDict({}))


    def test_contact_POST_fail(self):
        data = contact_post_request()
        data['email'] = ['notanemail']
        response = self.client.post(reverse("findshows:contact"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotEqual(response.context['form'].data, MultiValueDict({}))


class UserSettingsTests(TestCaseHelpers):
    def test_not_logged_in_user_settings_redirects(self):
        self.assert_redirects_to_login(reverse("findshows:user_settings"))

    def test_contact_GET(self):
        user = self.create_and_login_non_artist_user()
        response = self.client.get(reverse("findshows:user_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].instance, user)
