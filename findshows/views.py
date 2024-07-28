from django.views import generic
from django.http import HttpResponse
from django.shortcuts import render

from .models import Artist
from .spotify import search_spotify_artists

class ArtistView(generic.DetailView):
    model = Artist
    template_name = "findshows/view_artist.html"


def spotify_artist_search(request):
    return render(request, "findshows/spotify_artist_search.html")


def spotify_artist_search_results(request):
    # TODO prevent adding duplicate artist
    query = request.POST['spotify-search']
    if not query:
        return HttpResponse(b'')

    search_results = search_spotify_artists(query)
    for artist in search_results:
        for image in reversed(artist['images']):
            if image['height'] > 64 and image['width'] > 64:
                artist['image'] = image
                continue
    # TODO maybe filter images for smallest resolution > display value
    return render(request, "findshows/spotify_artist_search_results.html", {
        "spotify_artists": search_results
    })

# Create your views here.
