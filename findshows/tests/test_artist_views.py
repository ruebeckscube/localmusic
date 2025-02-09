import datetime

from django.db.models import QuerySet
from django.urls import reverse
from django.views.generic.dates import timezone_today

from findshows.tests.test_helpers import TestCaseHelpers, create_artist_t, create_concert_t, create_venue_t, image_file_t, create_user_profile_t
from findshows.views import is_artist_account


class IsArtistAccountTests(TestCaseHelpers):
    def test_is_artist_account(self):
        user_profile = self.create_and_login_artist_user()
        self.assertTrue(is_artist_account(user_profile.user))


    def test_is_not_artist_account(self):
        user_profile = self.create_and_login_non_artist_user()
        self.assertFalse(is_artist_account(user_profile.user))


    def test_not_logged_in(self):
        response = self.client.get(reverse("findshows:home"))
        user = response.wsgi_request.user
        self.assertFalse(is_artist_account(user))


class ManagedArtistListTests(TestCaseHelpers):
    def test_not_logged_in_managed_artist_list_redirects(self):
        self.assert_redirects_to_login(reverse("findshows:managed_artist_list"))


    def test_not_artist_user_managed_artist_list_redirects(self):
        self.create_and_login_non_artist_user()
        self.assert_redirects_to_login(reverse("findshows:managed_artist_list"))


    def test_one_artist_redirects_to_artist_page(self):
        artist = create_artist_t()
        self.create_and_login_artist_user(artist)
        response = self.client.get(reverse("findshows:managed_artist_list"))
        self.assertRedirects(response, reverse("findshows:view_artist", args=(artist.pk,)))


    def test_multiple_artists_gives_list(self):
        artist1 = create_artist_t()
        artist2 = create_artist_t()
        user = self.create_and_login_artist_user(artist1)
        user.managed_artists.add(artist2)
        response = self.client.get(reverse("findshows:managed_artist_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/managed_artist_list.html')
        self.assertEqual(set(response.context['artists']), {artist1, artist2})


class ArtistViewTests(TestCaseHelpers):
    def test_anonymous_view(self):
        artist = create_artist_t()
        response = self.client.get(reverse("findshows:view_artist", args=(artist.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/view_artist.html')
        self.assertFalse(response.context['can_edit'])
        self.assertEqual(response.context['artist'], artist)


    def test_non_artist_user_cant_edit(self):
        artist = create_artist_t()
        response = self.client.get(reverse("findshows:view_artist", args=(artist.pk,)))
        self.assertFalse(response.context['can_edit'])


    def test_artist_user_can_or_cant_edit(self):
        artist1 = create_artist_t()
        self.create_and_login_artist_user(artist1)
        artist2 = create_artist_t()
        response = self.client.get(reverse("findshows:view_artist", args=(artist1.pk,)))
        self.assertTrue(response.context['can_edit'])
        response = self.client.get(reverse("findshows:view_artist", args=(artist2.pk,)))
        self.assertFalse(response.context['can_edit'])


    def test_upcoming_concerts_filters_correctly(self):
        artist1 = create_artist_t()
        artist2 = create_artist_t()
        artist3 = create_artist_t()

        concert12past = create_concert_t(artists=[artist1, artist2], date=timezone_today() - datetime.timedelta(1))
        concert12today = create_concert_t(artists=[artist1, artist2], date=timezone_today())
        concert12future = create_concert_t(artists=[artist1, artist2], date=timezone_today() + datetime.timedelta(1))
        concert23future = create_concert_t(artists=[artist2, artist3], date=timezone_today() + datetime.timedelta(1))

        response = self.client.get(reverse("findshows:view_artist", args=(artist1.pk,)))

        self.assertEqual(set(response.context['upcoming_concerts']), {concert12today, concert12future})


def artist_post_request():
    return {
        'name': ['This is a test'],
        'bio': ['I sing folk songs and stuff'],
        'profile_picture': image_file_t(),
        'listen_links': ['https://soundcloud.com/measuringmarigolds/was-it-worth-the-kiss-demo\r\nhttps://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo\r\nhttps://soundcloud.com/measuringmarigolds/wax-wane-demo'],
        'similar_spotify_artists': ['{"id":"4chuPfKtATDZvbRLExsTp2","name":"Vashti Bunyan","img_url":"https://i.scdn.co/image/6b781cc1c4d486de2f7adad366b4bb95eb82b2ab"}',
                                    '{"id":"4M5nCE77Qaxayuhp3fVn4V","name":"Iron & Wine","img_url":"https://i.scdn.co/image/ab6761610000e5eb6554f29133d7e27979e009d7"}',
                                    '{"id":"5hW4L92KnC6dX9t7tYM4Ve","name":"Joni Mitchell","img_url":"https://i.scdn.co/image/68cfb061951dbd44c95422a54cb70baec0722ca3"}'],
        'socials_links_display_name': ['', '', ''],
        'socials_links_url': ['', '', ''],
        'initial-socials_links': ['[]'],
        'youtube_links': ['']
    }


# class EditArtistTests(TestCaseHelpers):
#     def test_edit_artist_doesnt_exist_GET(self):
#         self.create_and_login_artist_user()
#         response = self.client.get(reverse("findshows:edit_artist", args=(3,)))
#         self.assertEquals(response.status_code, 404)


#     def test_edit_artist_doesnt_exist_POST(self):
#         artist = create_artist_t()
#         venue = create_venue_t()
#         self.create_and_login_artist_user(artist)
#         response = self.client.post(reverse("findshows:edit_artist", args=(3,)), data=artist_post_request())
#         self.assertEquals(response.status_code, 404)


#     def test_user_doesnt_own_artist_GET(self):
#         user1 = self.create_and_login_artist_user()
#         user2 = create_user_profile_t()
#         concert = create_concert_t(created_by=user2)

#         response = self.client.get(reverse("findshows:edit_artist", args=(concert.pk,)))
#         self.assertEqual(response.status_code, 403)


#     def test_user_doesnt_own_artist_POST(self):
#         venue = create_venue_t()
#         artist = create_artist_t()
#         user1 = self.create_and_login_artist_user(artist)
#         user2 = create_user_profile_t()
#         artist_before = create_concert_t(created_by=user2)

#         response = self.client.post(reverse("findshows:edit_artist", args=(artist_before.pk,)), data=artist_post_request())
#         self.assertEqual(response.status_code, 403)

#         artist_after = Concert.objects.get(pk=artist_before.pk)
#         self.assertEqual(artist_before, artist_after)


#     def test_edit_artist_successful_GET(self):
#         user = self.create_and_login_artist_user()
#         artist = create_artist_t(created_by=user)
#         response = self.client.get(reverse("findshows:edit_artist", args=(artist.pk,)))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, 'findshows/pages/edit_artist.html')
#         self.assertEqual(response.context['form'].instance, artist)


#     def test_edit_artist_successful_POST(self):
#         venue1 = create_venue_t()
#         venue2 = create_venue_t()
#         artist = create_artist_t()
#         user = self.create_and_login_artist_user(artist)
#         artist_before = create_artist_t(created_by=user, artists=[artist], venue=venue1)

#         response = self.client.post(reverse("findshows:edit_artist", args=(artist_before.pk,)), data=artist_post_request())
#         self.assertRedirects(response, reverse('findshows:my_artist_list'))

#         concert_after = Concert.objects.get(pk=concert_before.pk)
#         self.assertEqual(concert_after.venue, venue2)
