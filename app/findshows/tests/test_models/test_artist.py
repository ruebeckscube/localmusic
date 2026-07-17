from findshows.tests.test_helpers import TestCaseHelpers


class SimilarityScoreTests(TestCaseHelpers):
    def test_no_similar_artists(self):
        artist = self.create_artist()
        self.assertEqual(artist.similarity_score(['123', '456']), 0)

    def test_no_searched_mbids(self):
        self.create_musicbrainz_artist('123', 'mb 123' , {'456': .7})
        artist = self.create_artist(similar_musicbrainz_artists=['123'])
        self.assertEqual(artist.similarity_score([]), 0)

    def test_scoring(self):
        self.create_musicbrainz_artist('123', 'mb 123' , {'999': .2, '888': .5})
        self.create_musicbrainz_artist('456', 'mb 456' , {'999': .4, '777': .8})
        self.create_musicbrainz_artist('789', 'mb 789' , {'888': .9})
        artist = self.create_artist(similar_musicbrainz_artists=['123', '456'])
        self.assertEqual(artist.similarity_score(['999', '888']), .275) # (.2+.5+.4+0)/4


class SaveTests(TestCaseHelpers):
    def test_social_links_url_massaging(self):
        artist = self.create_artist(socials_links=[
            ['HTTPS', 'https://this.shouldnt.change'],
            ['HTTP', 'http://nor.this'],
            ['No protocol', 'this.should.get/an/https/on/the/front'],
        ])
        self.assertEqual(artist.socials_links, [
            ['HTTPS', 'https://this.shouldnt.change'],
            ['HTTP', 'http://nor.this'],
            ['No protocol', 'https://this.should.get/an/https/on/the/front'],
        ])

    def test_social_links_email_massaging(self):
        artist = self.create_artist(socials_links=[
            ['With protocol', 'mailto:my@email.com'],
            ['Without protocol', 'another@test.email'],
        ])
        self.assertEqual(artist.socials_links, [
            ['With protocol', 'mailto:my@email.com'],
            ['Without protocol', 'mailto:another@test.email'],
        ])
