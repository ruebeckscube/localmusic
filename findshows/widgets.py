import json
from django.forms.fields import DateField, TimeField

from django.forms.widgets import Input

from findshows.models import Venue
import findshows.forms


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


class DatePickerField(DateField):
    widget=DatePickerWidget
    input_formats=('%Y-%m-%d',) # Just to be sure localization doesn't mess things up


class TimePickerWidget(Input):
    template_name="findshows/widgets/time_picker.html"

    def value_from_datadict(self, data, files, name):
        if data[name+"_hour"] == "" and data[name+"_minutes"] == "":
            return ""
        hour = int(data[name+"_hour"]) + 12*(data[name+"_ampm"]=="pm")
        return str(hour) + ":" + data[name+"_minutes"]  # any issues filter thru to validation

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if not context['widget']['value']:
            return context
        l = context['widget']['value'].split(':')
        if len(l) < 2:
            return context

        context['hour'], context['minutes'] = int(l[0]), l[1]
        if context['hour'] > 12:
            context['hour'] -= 12
            context['ampm'] = 'pm'
        else:
            context['ampm'] = 'am'

        return context


class TimePickerField(TimeField):
    widget=TimePickerWidget
    input_formats=('%H:%M',) # Just to be sure localization doesn't mess things up


class VenuePickerWidget(Input):
    template_name="findshows/widgets/venue_select.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['venue_name'] = Venue.objects.get(pk=context['widget']['value'])
        context['venue_form'] = findshows.forms.VenueForm()
        return context
