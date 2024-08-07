import json

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms.widgets import ClearableFileInput, FileInput, HiddenInput, Input

from findshows.models import Artist, UserProfile


class UserCreationFormE(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')

        if User.objects.filter(email=email).exists():
            msg = 'A user with that email already exists.'
            self.add_error('email', msg)

        return self.cleaned_data

    def save(self, commit=True):
        user = super(UserCreationForm, self).save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class SpotifyArtistSearchWidget(HiddenInput):
    template_name="findshows/spotify_artist_search.html"


class SocialsLinksWidget(Input):
    template_name="findshows/socials_links_widget.html"
    input_type="text"

    def value_from_datadict(self, data, files, name):
        l = list(zip(data.getlist(name + '_display_name'), data.getlist(name + '_url')))
        while ('','') in l:
            l.remove(('',''))
        return json.dumps(l)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        l = json.loads(value)
        context['widget']['socials_links'] = l + [('','')] * (3 - len(l))
        return context


class UserProfileCreationForm(forms.ModelForm):
    class Meta:
        model=UserProfile
        fields=("favorite_spotify_artists", "weekly_email")
        widgets={"favorite_spotify_artists": SpotifyArtistSearchWidget}


class ArtistEditForm(forms.ModelForm):
    class Meta:
        # TODO: should bands be able to edit their local status? if not how is it set?
        model=Artist
        fields=("name", "profile_picture", "bio", "youtube_links", "socials_links", "listen_links", "similar_spotify_artists")
        widgets={"similar_spotify_artists": SpotifyArtistSearchWidget,
                 "socials_links": SocialsLinksWidget}
