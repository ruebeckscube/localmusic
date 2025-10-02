import requests

from django.conf import settings
from django.utils.http import base64
from django.core.cache import cache


def _get_spotify_auth_headers():
    token = cache.get("spotify_access_token")
    if token is None:
        data = {'grant_type': 'client_credentials'}
        auth = base64.b64encode(settings.SPOTIFY_CLIENT_ID.encode() + b':'
                                + settings.SPOTIFY_CLIENT_SECRET.encode()).decode("utf-8")
        headers = {"Authorization": "Basic " + auth,
                   "Content-Type": "application/x-www-form-urlencoded"}
        r = requests.post('https://accounts.spotify.com/api/token', data, headers=headers)

        token = r.json()['access_token']
        timeout = r.json()['expires_in'] - 5
        cache.set("spotify_access_token", token, timeout)

    return {"Authorization": "Bearer " + token}


def set_spotify_artist_image(artist):
    for image in reversed(artist['images']):
        if image['height'] > 64 and image['width'] > 64:
            artist['image'] = image
            return


def search_spotify_artists(query):
    params = {"q": query, "type": "artist", "limit": 6}
    headers = _get_spotify_auth_headers()
    r = requests.get("https://api.spotify.com/v1/search", params, headers=headers)

    search_results = r.json()["artists"]["items"]
    for artist in search_results:
        set_spotify_artist_image(artist)
    return search_results


def get_spotify_artist_dict(spotify_artist_id):
    headers = _get_spotify_auth_headers()
    r = requests.get("https://api.spotify.com/v1/artists/" + spotify_artist_id,
                     headers=headers)
    artist = r.json()
    set_spotify_artist_image(artist)
    return {'id': spotify_artist_id,
            'img_url': artist['image']['url'],
            'name': artist['name']}


def get_related_spotify_artists(spotify_artist_id):
    return []

# Test artist IDs
# dylan = "74ASZWbe4lXaubB36ztrGX"
# seeger = "1P9syEkl41IFowWIJN7ZBY"
# woody = "4rAgFKtlTr66ic18YZZyF1"
# baez = "1EevBGfUh3RSQSGpluxgBm"
# joni = "5hW4L92KnC6dX9t7tYM4Ve"
# ochs = "3JhQGw54MOytJP3GZ8KNPo"
# abba = "0LcJLqbBmaGUft1e9Mm8HV"
# carly = "6sFIWsNpZYqfjUpaCgueju"
# chappell = "7GlBOeep6PqTfFi59PTUUN"

def relatedness_score(artists_and_relateds1, artists_and_relateds2):
    # Expecting a dictionary for each argument:
    # { artist1_spotify_id:
    #     [related_artist1_spotify_id,
    #      related_artist2_spotify_id,
    #      ...],
    #   artist2_spotify_id:
    #     [...]
    # }
    all_artists_1 = set().union(*artists_and_relateds1.values(), artists_and_relateds1.keys())
    all_artists_2 = set().union(*artists_and_relateds2.values(), artists_and_relateds2.keys())
    overlap = all_artists_1.intersection(all_artists_2)
    denominator = min(len(all_artists_1), len(all_artists_2))
    if denominator == 0:
        return 0
    return len(overlap) / denominator
