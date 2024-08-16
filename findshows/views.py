from django.contrib.auth import login
from django.core.mail import send_mail
from django.urls import reverse

from django.views import generic
from django.http import HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test



from .models import Artist, Concert
from .forms import ArtistEditForm, ConcertForm, UserCreationFormE, UserProfileCreationForm
from .spotify import search_spotify_artists


#################
## User Views ###
#################

def home(request):
    return render(request, "findshows/pages/home.html")

def user_settings(request):
    return HttpResponse("This will be settings")

def create_account(request):
    if request.method != 'POST':
        user_form = UserCreationFormE()
        profile_form = UserProfileCreationForm()
    else:
        user_form = UserCreationFormE(request.POST)
        profile_form = UserProfileCreationForm(request.POST)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()
            if "sendartistinfo" in request.POST:
                send_mail(
                    "Make an Artist page on Chicago Local Music",
                    "TODO make this a link to create an artist account linked to user",
                    "admin@chicagolocalmusic.com",
                    [user.email],
                    fail_silently=False,
                )
            login(request, user)
            return redirect('findshows:home')

    context = {'user_form': user_form,
               'profile_form': profile_form,
               }

    return render(request, 'registration/create_account.html', context)

###################
## Artist Views ###
###################

def is_artist_account(user):
    return (not user.is_anonymous
            and len(user.userprofile.managed_artists.all()) > 0)


@user_passes_test(is_artist_account)
def managed_artist_list(request):
    artists=request.user.userprofile.managed_artists.all()
    if len(artists)==1:
        return redirect(reverse('findshows:view_artist', args=[artists[0].pk]))
    return render(request, "findshows/pages/managed_artist_list.html", context = {
        "artists": artists,
    })


class ArtistView(generic.DetailView):
    model = Artist
    template_name = "findshows/pages/view_artist.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_edit"] = (not self.request.user.is_anonymous
                               and self.object in self.request.user.userprofile.managed_artists.all())
        return context


@login_required
def edit_artist(request, pk):
    artist = get_object_or_404(Artist, pk=pk)
    if artist not in request.user.userprofile.managed_artists.all():
        return redirect("/accounts/login/?next=%s" % request.path)

    if request.method != 'POST':
        form = ArtistEditForm(instance=artist)
    else:
        form = ArtistEditForm(request.POST, instance=artist)
        if form.is_valid():
            form.save()
            return redirect(reverse('findshows:view_artist', args=[pk]))

    context = {'form': form,
               'pk': pk }

    return render(request, 'findshows/pages/edit_artist.html', context)


#####################
## Concert Views ####
#####################

@login_required
def edit_concert(request, pk=None):
    if pk is None:
        concert = Concert()
    else:
        concert = get_object_or_404(Concert, pk=pk)
    # TODO check permissions to edit this concert... and THINK about who the heck should have access. Any listed band??? really??

    if request.method != 'POST':
        form = ConcertForm(instance=concert)
    else:
        form = ConcertForm(request.POST, instance=concert)
        if form.is_valid():
            form.save()
            return redirect(reverse('findshows:my_concert_list'))

    context = {'form': form,
               'pk': pk}

    return render(request, 'findshows/pages/edit_concert.html', context)


@user_passes_test(is_artist_account)
def my_concert_list(request):
    artists=request.user.userprofile.managed_artists.all()
    concerts=set(c for a in artists for c in a.concert_set.all()) # Set removes duplicates
    return render(request, "findshows/pages/concert_list_for_artist.html", context = {
        "concerts": concerts,
    })


#########################
## Spotify search tool ##
#########################


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
    return render(request, "findshows/htmx/spotify_artist_search_results.html", {
        "spotify_artists": search_results
    })
