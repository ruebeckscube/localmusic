from django.test import TestCase
from findshows.models import Ages

from findshows.tests.test_helpers import create_artist_t, create_concert_t, create_musicbrainz_artist_t, create_venue_t


class ConcertTests(TestCase):
    def test_relevance_score(self):
        create_musicbrainz_artist_t('123', 'mb 123' , {'999': .2, '888': .5})
        create_musicbrainz_artist_t('456', 'mb 456' , {'999': .4, '777': .8})
        create_musicbrainz_artist_t('789', 'mb 789' , {'888': .7})

        artist1 = create_artist_t(similar_musicbrainz_artists=['123'])
        artist2 = create_artist_t(similar_musicbrainz_artists=['456'])
        artist3 = create_artist_t(similar_musicbrainz_artists=['789'])

        concert = create_concert_t(artists=[artist1, artist2, artist3])

        self.assertEqual(concert.relevance_score(['999', '888']), .3) # ((.2+.5)/2 + (.4+0)/2 + (0+.7)/2)/3

    def test_sorted_artists(self):
        artist1 = create_artist_t()
        artist2 = create_artist_t()
        artist3 = create_artist_t()

        concert = create_concert_t(artists=[artist2, artist3, artist1])
        self.assertEqual(list(concert.sorted_artists), [artist2, artist3, artist1])

    def test_ages_with_default(self):
        venue = create_venue_t(ages=Ages.ALL_AGES)
        concert = create_concert_t(venue=venue) # defaults to no ages set

        self.assertEqual(concert.ages_with_default, Ages.ALL_AGES.label)
        concert.ages = Ages.TWENTYONE
        self.assertEqual(concert.ages_with_default, Ages.TWENTYONE.label)
