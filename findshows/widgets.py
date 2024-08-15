import json

from django.forms.widgets import Input


class SpotifyArtistSearchWidget(Input):
    template_name="findshows/widgets/spotify_artist_search.html"
    input_type="hidden"

    def __init__(self, max_artists=3, **kwargs):
        super().__init__(**kwargs)
        self.max_artists = max_artists

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['max_artists'] = self.max_artists
        return context


class SocialsLinksWidget(Input):
    template_name="findshows/widgets/socials_links_widget.html"
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


class DatePickerWidget(Input):
    template_name="findshows/widgets/date_picker.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if context['widget']['value'] is None:
            context['widget']['value'] = ''
        return context
