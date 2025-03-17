from findshows.models import Ages

from findshows.tests.test_helpers import TestCaseHelpers


class ConcertTests(TestCaseHelpers):
    def test_relevance_score(self):
        self.create_musicbrainz_artist('123', 'mb 123' , {'999': .2, '888': .5})
        self.create_musicbrainz_artist('456', 'mb 456' , {'999': .4, '777': .8})
        self.create_musicbrainz_artist('789', 'mb 789' , {'888': .7})

        artist1 = self.create_artist(similar_musicbrainz_artists=['123'])
        artist2 = self.create_artist(similar_musicbrainz_artists=['456'])
        artist3 = self.create_artist(similar_musicbrainz_artists=['789'])

        concert = self.create_concert(artists=[artist1, artist2, artist3])

        self.assertEqual(concert.relevance_score(['999', '888']), .3) # ((.2+.5)/2 + (.4+0)/2 + (0+.7)/2)/3

    def test_sorted_artists(self):
        artist1 = self.create_artist()
        artist2 = self.create_artist()
        artist3 = self.create_artist()

        concert = self.create_concert(artists=[artist2, artist3, artist1])
        self.assertEqual(list(concert.sorted_artists), [artist2, artist3, artist1])

    def test_ages_with_default(self):
        venue = self.create_venue(ages=Ages.ALL_AGES)
        concert = self.create_concert(venue=venue) # defaults to no ages set

        self.assertEqual(concert.ages_with_default, Ages.ALL_AGES.label)
        concert.ages = Ages.TWENTYONE
        self.assertEqual(concert.ages_with_default, Ages.TWENTYONE.label)
