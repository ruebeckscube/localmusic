import requests
from time import sleep
import warnings

from django.conf import settings


AUTH_HEADER = {
    "User-Agent": settings.USER_AGENT_HEADER,
    "Authorization": "Token {0}".format(settings.MUSICBRAINZ_TOKEN)
}


def get_similar_artists(mbid=None):
    """Similarity scores from the Musicbrainz algorithm, described here:
    https://community.metabrainz.org/t/how-does-similar-artists-work/678642/3

    Returns a dictionary of {mbid: similarity_score}
    """
    url = "https://labs.api.listenbrainz.org/similar-artists/json"
    params = {
        "artist_mbids": mbid,
        "algorithm": "session_based_days_7500_session_300_contribution_5_threshold_10_limit_100_filter_True_skip_30"
    }
    response = requests.get(url, params, headers=AUTH_HEADER)

    if response.status_code != 200:
        warnings.warn("MusicBrainz API for finding similar artists was called unsuccessfully.")
        return None

    artist_list = response.json()
    if not artist_list:
        return {}
    max_score = max(a['score'] for a in artist_list)
    return {a['artist_mbid']: a['score']/max_score for a in artist_list}


# Test artist IDs
# Nanci Griffith 'b9ffd0e7-7f95-46db-bc1c-8094d459f084'
# Mary Chapin Carpenter 'ba1bf556-2af2-4772-835f-ed2e15070758'

