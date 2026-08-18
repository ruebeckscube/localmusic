from findshows.models import ArtistInviteLinkCode
from findshows.tests.test_helpers import TestCaseHelpers


class InviteCodeStorageTests(TestCaseHelpers):
    def test_correct_code(self):
        link_code = ArtistInviteLinkCode()
        link_code._generate_code()
        self.assertTrue(link_code.check_code(link_code.code_cache))

    def test_incorrect_code(self):
        link_code = ArtistInviteLinkCode()
        link_code._generate_code()
        self.assertFalse(link_code.check_code("not_the_code"))

    def test_not_storing_raw_code(self):
        link_code = ArtistInviteLinkCode()
        link_code._generate_code()
        self.assertNotIn(link_code.code_cache, link_code.code_hashed)
