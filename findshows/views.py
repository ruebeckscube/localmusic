# from django.shortcuts import render
# from django.shortcuts import get_object_or_404
from django.views import generic

from .models import Artist

class ArtistView(generic.DetailView):
    model = Artist
    template_name = "findshows/view_artist.html"

# Create your views here.
