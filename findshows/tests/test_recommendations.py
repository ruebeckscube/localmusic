import datetime
from django.core import mail
from django.urls import reverse
from django.utils.timezone import now
from findshows.email import send_rec_email
from findshows.models import MusicBrainzArtist
from findshows.tests.test_helpers import TestCaseHelpers, concert_GET_params


class RecommendationTests(TestCaseHelpers):
    @classmethod
    def setUpTestData(cls):
        # Setting up clusters of similar MusicBrainz artists, where each artist
        # is .7 similar to other artists in its cluster and unrelated to other clusters.
        # each artist has mbid/is named <cluster number>-<artist number> for easy referencing.
        # e.g. 0-0, 0-2 are in the same cluster, 1-0 is in a different cluster
        tomorrow = now() + datetime.timedelta(1)
        clusters = 5
        mb_artists_per_cluster = 3
        mb_artists = (MusicBrainzArtist(
            mbid=f'{c}-{a}',
            name=f'{c}-{a}',
            similar_artists={s_mbid: .7 for s_mbid in (f'{c}-{a_s}'
                                                       for a_s in range(mb_artists_per_cluster)
                                                       if a_s != a)},
            similar_artists_cache_datetime=tomorrow,
        )
                      for a in range(mb_artists_per_cluster)
                      for c in range(clusters))
        MusicBrainzArtist.objects.bulk_create(mb_artists)

        # Creating (local) artists that are similar to each cluster
        artist_0_0 = cls.create_artist("Cluster-0 Artist-0", similar_musicbrainz_artists=[f'{0}-{a}' for a in range(3)])
        artist_0_1 = cls.create_artist("Cluster-0 Artist-1", similar_musicbrainz_artists=[f'{0}-{a}' for a in range(3)])
        artist_0_2 = cls.create_artist("Cluster-0 Artist-2", similar_musicbrainz_artists=[f'{0}-{a}' for a in range(3)])
        artist_1_0 = cls.create_artist("Cluster-1 Artist-0", similar_musicbrainz_artists=[f'{1}-{a}' for a in range(3)])
        artist_1_1 = cls.create_artist("Cluster-1 Artist-1", similar_musicbrainz_artists=[f'{1}-{a}' for a in range(3)])
        artist_2_0 = cls.create_artist("Cluster-2 Artist-0", similar_musicbrainz_artists=[f'{2}-{a}' for a in range(3)])
        artist_2_1 = cls.create_artist("Cluster-2 Artist-1", similar_musicbrainz_artists=[f'{2}-{a}' for a in range(3)])
        artist_3_0 = cls.create_artist("Cluster-3 Artist-0", similar_musicbrainz_artists=[f'{3}-{a}' for a in range(3)])

        cls.concert1 = cls.create_concert(artists=[artist_0_0, artist_0_1, artist_0_2])
        cls.concert2 = cls.create_concert(artists=[artist_0_0, artist_0_1, artist_1_0])
        cls.concert3 = cls.create_concert(artists=[artist_0_0, artist_1_0, artist_1_1])
        cls.concert4 = cls.create_concert(artists=[artist_2_0, artist_2_1, artist_3_0])


    def test_similarity_sorting(self):
        response = self.client.get(reverse('findshows:concert_search_results'),
                                   concert_GET_params(musicbrainz_artists=['0-0', '0-1']))
        self.assertEqual(response.context['concerts'], [self.concert1, self.concert2, self.concert3, self.concert4])

        response = self.client.get(reverse('findshows:concert_search_results'),
                                   concert_GET_params(musicbrainz_artists=['1-2']))
        self.assertEqual(response.context['concerts'][:2], [self.concert3, self.concert2])

        response = self.client.get(reverse('findshows:concert_search_results'),
                                   concert_GET_params(musicbrainz_artists=['2-0']))
        self.assertEqual(response.context['concerts'][0], self.concert4)

        # Results are random, just checking it doesn't error out
        response = self.client.get(reverse('findshows:concert_search_results'),
                                   concert_GET_params(musicbrainz_artists=['']))


    def test_email_concert_inclusion(self):
        self.create_user_profile(favorite_musicbrainz_artists=['0-0', '0-1', '0-2'], email="user1@em.ail")
        self.create_user_profile(favorite_musicbrainz_artists=['4-0', '4-1', '4-2'], email="user2@em.ail")
        self.create_user_profile(favorite_musicbrainz_artists=[], email="user3@em.ail")
        self.create_user_profile(favorite_musicbrainz_artists=['0-0', '0-1', '0-2'], email="user4@em.ail", weekly_email=False)

        send_rec_email()
        self.assert_emails_sent(3)
        for message in mail.outbox:
            match message.recipients():
                case ['user1@em.ail']: # Gets the two recs
                    self.assert_concert_link_in_message_html(self.concert1, message)
                    self.assert_concert_link_in_message_html(self.concert2, message)
                case ['user2@em.ail'] | ['user3@em.ail']: # Gets randomized recs
                    self.assert_concert_link_in_message_html(self.concert1, message)
                    self.assert_concert_link_in_message_html(self.concert2, message)
                    self.assert_concert_link_in_message_html(self.concert3, message)
                    self.assert_concert_link_in_message_html(self.concert4, message)
                case ['user4@em.ail']:
                    self.assertFalse("User 4 should not receive an email")
