'''Tests permissions for all urls'''
from itertools import chain
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from findshows.models import ArtistVerificationStatus
from findshows.tests.test_helpers import TestCaseHelpers


PUBLIC_URLS_NO_PK = (
    "home",
    "about",
    "artist_faq",
    "contact",
    "concert_search",
    "musicbrainz_artist_search_results",
    "venue_search_results",
    "artist_search_results",
    "terms_of_service",
)
PUBLIC_URLS_WITH_PK = (
    "view_artist",
    "view_concert",
)
LOGGED_IN_URLS = (
    "user_settings",
    "link_artist",
    "create_artist",
)
ARTIST_URLS_NO_PK = (
    "artist_dashboard",
    "create_venue",
    "create_temp_artist",
    "create_concert",
)
ARTIST_URLS_WITH_PK = (
    "edit_artist",
    "edit_concert",
    "cancel_concert",
    "uncancel_concert",
    "manage_artist_access",
    "resend_invite",
)
MOD_URLS_NO_PK = (
    "mod_dashboard",
    "mod_daily_digest",
    "mod_queue",
    "mod_outstanding_invites",
    "mod_text_customization",
)
MOD_URLS_WITH_PK = (
    "venue_verification",
    "artist_verification_buttons",
)

class PermissionsTests(TestCaseHelpers):
    def assert_view_permissions(self, url_set, expected_to_have_permission, pk=None):
        for url_name in url_set:
            url = reverse(f"findshows:{url_name}", args=[pk] if pk else [])
            response = self.client.get(url)

            if expected_to_have_permission:
                self.assertEqual(response.status_code, 200, msg=url_name)
                self.assertTemplateNotUsed('findshows/htmx/modal_error_msg.html', msg_prefix=url_name)
            else:
                self.assertIn(response.status_code, (200, 302, 403), msg=url_name)
                match response.status_code:
                    case 200:
                        self.assertIn("htmx", url) # 200 is only an allowable error response for modal stuff
                        self.assertTemplateUsed('findshows/htmx/modal_error_msg.html', msg_prefix=url_name)
                    case 302:
                        self.assertRedirects(response, reverse('login', query={'next': url}), msg_prefix=url_name)
                    case 403:
                        pass #this is a rock wall, no additional conditions


    def assert_generic_permissions(self, allowed_no_pk, allowed_pk, disallowed_no_pk, disallowed_pk):
        self.assert_view_permissions(allowed_no_pk, True)
        self.assert_view_permissions(allowed_pk, True, pk=self.pk)
        self.assert_view_permissions(disallowed_no_pk, False)
        self.assert_view_permissions(disallowed_pk, False, pk=self.pk)

    def assert_permissions_for_hidden_records(self, allowed, disallowed):
        self.assert_view_permissions(allowed, True, pk=self.other_pk)
        self.assert_view_permissions(disallowed, False, pk=self.other_pk)

    def login_with_status(self, status: ArtistVerificationStatus):
        self.userprofile.artist_verification_status = status
        self.userprofile.save()
        self.client.login(email=self.email, password=self.password)


    def setUp(self):
        # Hacky but using the same pk for everything for easy iteration
        self.pk = 1000
        self.email = "permissions@test.edu"
        self.password = "12345"
        self.userprofile = self.create_user_profile(pk=self.pk, email=self.email, password=self.password, artist_verification_status=ArtistVerificationStatus.VERIFIED)
        self.venue = self.create_venue(pk=self.pk)
        self.artist = self.create_artist(pk=self.pk, created_by=self.userprofile)
        self.userprofile.managed_artists.add(self.artist)
        self.concert = self.create_concert(pk=self.pk, venue = self.venue, artists = [self.artist], created_by=self.userprofile)
        self.ali = self.create_artist_linking_info(pk=self.pk, created_by=self.userprofile)

        self.other_pk = 1001
        self.other_email = "has@hidden.rec"
        self.other_password = "12345"
        self.other_user_profile = self.create_user_profile(pk=self.other_pk, email=self.other_email, password=self.other_password, artist_verification_status=ArtistVerificationStatus.UNVERIFIED)
        self.other_artist = self.create_artist(pk=self.other_pk, created_by=self.other_user_profile)
        self.other_user_profile.managed_artists.add(self.other_artist)
        self.other_concert = self.create_concert(pk=self.other_pk, created_by=self.other_user_profile, artists=[self.other_artist])

        return super().setUp()


    def test_user_not_logged_in(self):
        self.assert_generic_permissions(
            PUBLIC_URLS_NO_PK,
            PUBLIC_URLS_WITH_PK,
            chain(LOGGED_IN_URLS, ARTIST_URLS_NO_PK, MOD_URLS_NO_PK),
            chain(ARTIST_URLS_WITH_PK, MOD_URLS_WITH_PK))
        self.assert_permissions_for_hidden_records((), PUBLIC_URLS_WITH_PK)


    def test_non_artist(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        self.assert_generic_permissions(
            chain(PUBLIC_URLS_NO_PK, LOGGED_IN_URLS),
            PUBLIC_URLS_WITH_PK,
            chain(ARTIST_URLS_NO_PK, MOD_URLS_NO_PK),
            chain(ARTIST_URLS_WITH_PK, MOD_URLS_WITH_PK))
        self.assert_permissions_for_hidden_records((), PUBLIC_URLS_WITH_PK)

    def test_deverified_artist(self):
        self.login_with_status(ArtistVerificationStatus.DEVERIFIED)

        deverified_exceptions = ("create_artist",)
        logged_in_besides_deverified = (url for url in LOGGED_IN_URLS if url not in deverified_exceptions)

        self.assert_generic_permissions(
            chain(PUBLIC_URLS_NO_PK, logged_in_besides_deverified),
            PUBLIC_URLS_WITH_PK,
            chain(ARTIST_URLS_NO_PK, MOD_URLS_NO_PK, deverified_exceptions),
            chain(ARTIST_URLS_WITH_PK, MOD_URLS_WITH_PK))
        self.assert_permissions_for_hidden_records((), PUBLIC_URLS_WITH_PK)

    def assert_verified_equiv_permissions(self):
        self.assert_generic_permissions(
            chain(PUBLIC_URLS_NO_PK, LOGGED_IN_URLS, ARTIST_URLS_NO_PK),
            chain(PUBLIC_URLS_WITH_PK, ARTIST_URLS_WITH_PK),
            chain(MOD_URLS_NO_PK),
            chain(MOD_URLS_WITH_PK))
        self.assert_permissions_for_hidden_records((), PUBLIC_URLS_WITH_PK)

        # Checks that the artist can't access records they don't own
        self.create_artist(pk=9999)
        self.create_concert(pk=9999)
        self.create_artist_linking_info(pk=9999)
        self.assert_view_permissions(ARTIST_URLS_WITH_PK, False, pk=9999)


    def test_unverified_local_artist(self):
        self.login_with_status(ArtistVerificationStatus.UNVERIFIED)
        self.assert_verified_equiv_permissions()


    def test_verified_local_artist(self):
        self.login_with_status(ArtistVerificationStatus.VERIFIED)
        self.assert_verified_equiv_permissions()


    def test_invited_local_artist(self):
        self.login_with_status(ArtistVerificationStatus.INVITED)
        self.assert_verified_equiv_permissions()

    def test_owner_of_hidden_records(self):
        self.client.login(email=self.other_email, password=self.other_password)
        self.assert_permissions_for_hidden_records(PUBLIC_URLS_WITH_PK, ())


    def test_non_local_artist(self):
        self.login_with_status(ArtistVerificationStatus.NOT_LOCAL)
        allowed_artist_no_pk = ("artist_dashboard",)
        disallowed_artist_no_pk = (url for url in ARTIST_URLS_NO_PK if url not in allowed_artist_no_pk)
        allowed_artist_with_pk = ("edit_artist", "manage_artist_access")
        disallowed_artist_with_pk = (url for url in ARTIST_URLS_WITH_PK if url not in allowed_artist_with_pk)
        self.assert_generic_permissions(
            chain(PUBLIC_URLS_NO_PK, LOGGED_IN_URLS, allowed_artist_no_pk),
            chain(PUBLIC_URLS_WITH_PK, allowed_artist_with_pk),
            chain(MOD_URLS_NO_PK, disallowed_artist_no_pk),
            chain(MOD_URLS_WITH_PK, disallowed_artist_with_pk))
        self.assert_permissions_for_hidden_records((), PUBLIC_URLS_WITH_PK)

    def test_mod(self):
        self.login_static_user(self.StaticUsers.MOD_USER)

        self.assert_generic_permissions(
            chain(PUBLIC_URLS_NO_PK, LOGGED_IN_URLS, MOD_URLS_NO_PK),
            chain(PUBLIC_URLS_WITH_PK, MOD_URLS_WITH_PK),
            ARTIST_URLS_NO_PK,
            ARTIST_URLS_WITH_PK)
        self.assert_permissions_for_hidden_records(PUBLIC_URLS_WITH_PK, ())

    def test_admin(self):
        self.create_user_profile(email="admin@admin.net", password='12345', is_staff=True)
        self.client.login(email="admin@admin.net", password='12345')

        # Critically this includes yes permissions for editing artists/concrets not belonging to this user
        artist_urls_besides_dashboard = (url for url in ARTIST_URLS_NO_PK if url != "artist_dashboard")
        self.assert_generic_permissions(
            chain(PUBLIC_URLS_NO_PK, LOGGED_IN_URLS, artist_urls_besides_dashboard, MOD_URLS_NO_PK),
            chain(PUBLIC_URLS_WITH_PK, ARTIST_URLS_WITH_PK, MOD_URLS_WITH_PK),
            ("artist_dashboard",),
            ())
        self.assert_permissions_for_hidden_records(PUBLIC_URLS_WITH_PK, ())


    def assert_404s(self, url_set, pk):
        for url_name in url_set:
            url = reverse(f"findshows:{url_name}", args=[pk])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404, msg=url_name)


    def test_404s(self):
        self.create_user_profile(email="admin@admin.net", password='12345', is_staff=True)
        self.client.login(email="admin@admin.net", password='12345')

        self.assert_404s(chain(PUBLIC_URLS_WITH_PK, ARTIST_URLS_WITH_PK, MOD_URLS_WITH_PK), self.pk*3)


    def all_url_patterns(self, url_patterns=None, namespace=""):
        """
        Yield tuples of (URLPattern, namespace) for all URLPattern objects in the
        given Django URLconf, or the default one if none is provided.
        """
        if url_patterns is None:
            url_patterns = get_resolver().url_patterns

        for pattern in url_patterns:
            if isinstance(pattern, URLPattern):
                yield pattern, namespace
            elif isinstance(pattern, URLResolver):
                if pattern.namespace:
                    if namespace:
                        namespace = f"{namespace}:{pattern.namespace}"
                    else:
                        namespace = pattern.namespace
                yield from self.all_url_patterns(pattern.url_patterns, namespace)
            else:
                raise TypeError(f"Unexpected pattern type: {type(pattern)} in {namespace}")


    def test_all_urls_accounted_for(self):
        all_here = chain(
            PUBLIC_URLS_NO_PK,
            PUBLIC_URLS_WITH_PK,
            LOGGED_IN_URLS,
            ARTIST_URLS_NO_PK,
            ARTIST_URLS_WITH_PK,
            MOD_URLS_NO_PK,
            MOD_URLS_WITH_PK,
        )
        all_existing = (pattern.name
                        for pattern, namespace in self.all_url_patterns()
                        if namespace=="findshows")
        self.assert_equal_as_sets(all_here, all_existing)
