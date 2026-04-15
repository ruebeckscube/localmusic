from datetime import timedelta
from itertools import zip_longest

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import BaseUserCreationForm
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import models
from django.forms.widgets import TimeInput
from django.views.generic.dates import timezone_today
from django.conf import settings
from multiselectfield.forms.fields import MultiSelectFormField
from captcha.fields import CaptchaField

from findshows.models import MAX_UPLOADED_IMAGE_SIZE_IN_MB, Artist, Concert, ConcertTags, LabeledURLsValidator, ListenLink, MusicBrainzArtist, UserProfile, Venue, YoutubeLink
from findshows.widgets import ArtistAccessWidget, BillWidget, DatePickerField, DatePickerWidget, EmbedLinkField, ImageInput, SocialsLinksWidget, MusicBrainzArtistSearchWidget, StyledSelect, VenuePickerWidget

User = get_user_model()

def add_default_styling_to_fields(fields):
    field_type_to_css_class = {
        forms.CharField: 'textinput',
        forms.URLField: 'textinput',
        forms.EmailField: 'textinput',
        MultiSelectFormField: 'accent-clickable',
        forms.BooleanField: 'accent-clickable mr-auto',
        CaptchaField: 'textinput',
        forms.TimeField: 'textinput',
    }
    for field in fields:
        field.widget.attrs.update({
            'class': field_type_to_css_class.get(type(field))
        })


# Have to duplicate this because of how the base classes are written
# (they don't call super in init, so a mixin version of this wouldn't get init called)
class DefaultStylingForm(forms.Form):
    required_css_class = "required"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_default_styling_to_fields(self.fields.values())


class DefaultStylingModelForm(forms.ModelForm):
    required_css_class = "required"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_default_styling_to_fields(self.fields.values())


class UserCreationFormE(BaseUserCreationForm):
    required_css_class = "required"
    captcha = CaptchaField()

    class Meta:
        model = User
        fields = ("email", "password1", "password2")
        field_classes = {"email": forms.EmailField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_default_styling_to_fields(self.fields.values())


class UserProfileForm(DefaultStylingModelForm):
    class Meta:
        model=UserProfile
        fields=("favorite_musicbrainz_artists", "preferred_concert_tags", "weekly_email")
        widgets={"favorite_musicbrainz_artists": MusicBrainzArtistSearchWidget(max_artists=settings.MAX_USER_ARTISTS)}


def validate_image(image):
    if image.size > MAX_UPLOADED_IMAGE_SIZE_IN_MB*1024*1024:
        raise ValidationError("Image file too large")
    return image


LISTEN_LINK_HELP="""A preview player for all songs will be displayed on your
artist page, and the first track will be displayed on concerts. Please
provide either one album link or up to three song links on separate lines.
Supports Spotify, Bandcamp, and SoundCloud links. For Spotify and SoundCloud,
artist/playlist links work as well. """


class ArtistEditForm(DefaultStylingModelForm):
    listen_links=EmbedLinkField(num_links=3, help_text=LISTEN_LINK_HELP,
                                placeholder="https://artist.bandcamp.com/track/track-title")
    youtube_links=EmbedLinkField(num_links=2, required=False,
                                 help_text="Youtube videos will be embedded on your artist page.",
                                 placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    class Meta:
        model=Artist
        fields=("name", "profile_picture", "bio", "socials_links", "similar_musicbrainz_artists")
        widgets={
            "similar_musicbrainz_artists": MusicBrainzArtistSearchWidget,
            "socials_links": SocialsLinksWidget,
            "profile_picture": ImageInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.id:
            self.fields['listen_links'].initial = [link.resource_url
                                                   for link in self.instance.listenlink_set.order_by('order')]
            self.fields['youtube_links'].initial = [link.resource_url
                                                    for link in self.instance.youtubelink_set.order_by('order')]
        else:
            self.fields['listen_links'].initial = []
            self.fields['youtube_links'].initial = []


    def clean_socials_links(self):
        socials_links = self.cleaned_data['socials_links']
        LabeledURLsValidator()(socials_links)
        return socials_links


    def clean_profile_picture(self):
        return validate_image(self.cleaned_data['profile_picture'])


    def _embed_cleaner(self, embedClass, clean_links):
        cache = []
        for idx, resource_url in enumerate(clean_links):
            link = embedClass(resource_url=resource_url, order=idx+1)
            link.update_iframe_url() # This raises various ValidationErrors if any piece of API calls fail
            cache.append(link)
        return cache


    def clean_listen_links(self):
        self.cleaned_data['listen_links_cache'] = self._embed_cleaner(ListenLink, self.cleaned_data['listen_links'])
        if (len(self.cleaned_data['listen_links_cache']) > 1
            and any(l.get_type()==ListenLink.ALBUM for l in self.cleaned_data['listen_links_cache'])):
            raise ValidationError("Please enter links to either (a) one album or (b) one or more individual tracks.")


    def clean_youtube_links(self):
        self.cleaned_data['youtube_links_cache'] = self._embed_cleaner(YoutubeLink, self.cleaned_data['youtube_links'])


    def clean_similar_musicbrainz_artists(self):
        mb_artists = self.cleaned_data['similar_musicbrainz_artists']
        no_similar_artists = [mba.name
                              for mba in mb_artists
                              if not mba.get_similar_artists()]
        if no_similar_artists:
            raise ValidationError(f"We do not currently have any similarity data on the following artists: {','.join(no_similar_artists)}. Please select another to make sure you show up in search results!")
        return mb_artists


    def save_embed_links(self, artist, new_links, old_links):
        # Must be called after artist save
        for new_link, old_link in zip_longest(new_links, old_links):
            # Just a partially optimized way of making current state exactly reflect form input
            if old_link is not None:
                if new_link is None:
                    old_link.delete()
                    continue
                if new_link.iframe_url == old_link.iframe_url:
                    continue
                old_link.delete()
            if new_link is not None:
                new_link.artist = artist
                new_link.save()


    def save(self, commit = True):
        artist = super().save(commit=False)
        artist.is_temp_artist = False
        if commit:
            artist.save()
            self.save_m2m()
            self.save_embed_links(artist, self.cleaned_data['listen_links_cache'], artist.listenlink_set.order_by('order'))
            self.save_embed_links(artist, self.cleaned_data['youtube_links_cache'], artist.youtubelink_set.order_by('order'))
        return artist


class ConcertForm(DefaultStylingModelForm):
    date = DatePickerField()
    # NOT a model field, we parse this and save to the artists field through the SetOrder through-model
    bill = forms.JSONField(widget=BillWidget, help_text="""The artists will be
    listed in the order they're entered; the artist performing first should be
    at the bottom of the bill and the artist performing last should be at the
    top of the bill. If the artist does not already have a profile, invite them
    to create one with the Invite Artist button.""")

    class Meta:
        model=Concert
        fields=("poster", "date", "doors_time", "start_time", "end_time", "venue", "ages", "ticket_link", "ticket_description", "tags", "description")
        widgets={
            "venue": VenuePickerWidget,
            "poster": ImageInput,
            "ages": StyledSelect,
            "doors_time": TimeInput({'type': 'time'}, format='%H:%M'),
            "start_time": TimeInput({'type': 'time'}, format='%H:%M'),
            "end_time": TimeInput({'type': 'time'}, format='%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['placeholder'] = 'Emojis encouraged ✌️'
        if self.instance.id:
            self.fields['bill'].initial = [{'id': a.pk, 'name': a.name}
                                           for a in self.instance.sorted_artists]
        else:
            self.fields['bill'].initial = []

    def set_editing_user(self, user):
        self.editing_user = user


    def clean_venue(self):
        venue = self.cleaned_data['venue']
        if venue.declined_listing:
            self.add_error('venue', 'You cannot list a show at a venue that has declined listings.')
        return venue


    def clean_date(self):
        date = self.cleaned_data['date']
        if date > timezone_today() + timedelta(settings.MAX_FUTURE_CONCERT_WEEKS * 7):
            self.add_error('date', f'Date cannot be more than {settings.MAX_FUTURE_CONCERT_WEEKS} weeks in the future.')
        return date


    def clean_poster(self):
        return validate_image(self.cleaned_data['poster'])


    def clean(self):
        cleaned_data = super().clean() or {}

        local_user_artists = set(str(a.id)
                                 for a in self.editing_user.userprofile.managed_artists.all()
                                 if a.local)
        if not local_user_artists.intersection(str(a['id']) for a in cleaned_data['bill']):
            self.add_error('bill', """The bill must include one of the local
            artists that your account manages.""")

        venue = cleaned_data.get("venue")
        date = cleaned_data.get("date")
        if venue and date:
            conflict_concerts = Concert.objects.filter(venue=venue, date=date).exclude(cancelled=True)
            if self.instance:
                conflict_concerts = conflict_concerts.exclude(pk=self.instance.pk)
            if conflict_concerts.count():
                self.add_error(None, """There is already a show in the database
                               for the specified venue and date. If you think
                               this is in error, or there are in fact two events
                               on the same date, please contact site admins for
                               an override.""")
        return cleaned_data

    def save(self, commit = True): # saving this without a commit is gonna be weird, hope it doesn't happen
        concert = super().save(commit=False)

        if commit and not concert.id:
            concert.save()

        if concert.id:
            concert.artists.clear()
            for idx, artist_dict in enumerate(self.cleaned_data['bill']):  # Assuming all new artist records have been saved
                if artist_dict['id']:
                    concert.artists.add(artist_dict['id'], through_defaults = {'order_number': idx})

        if commit:
            concert.save()

        return concert


class VenueForm(DefaultStylingModelForm):
    prefix = "venue"
    use_required_attribute = False

    class Meta:
        model=Venue
        fields=("name", "ages", "website")
        widgets={"ages": StyledSelect}


class ArtistAccessForm(forms.Form):
    users = forms.JSONField(widget=ArtistAccessWidget, required=False)
    prefix = "artist_access"


    @classmethod
    def populate_intial(cls, current_user_profile, artist):
        form = cls()
        form.fields['users'].initial = [
            {'email': user_profile.user.email, 'type': ArtistAccessWidget.Types.LINKED.value}
            for user_profile in artist.managing_users.all()
            if user_profile != current_user_profile
        ]
        form.fields['users'].initial.extend(
            {'email': ali.invited_email, 'type': ArtistAccessWidget.Types.UNLINKED.value}
            for ali in artist.artistlinkinginfo_set.all()
        )
        return form

    @classmethod
    def user_json_has_valid_email(cls, user_json):
        try:
            EmailValidator()(user_json['email'])
        except ValidationError:
            return False
        return True


    def clean_users(self):
        invalid_emails = ','.join(u['email']
                                  for u in self.cleaned_data['users']
                                  if not self.user_json_has_valid_email(u))
        if invalid_emails:
            self.add_error(None,
                           f"Invalid email addresses: {invalid_emails}.")
        return self.cleaned_data['users']


class TempArtistForm(DefaultStylingModelForm):
    prefix = "temp_artist"
    use_required_attribute = False
    email=forms.EmailField(required=True, help_text="""Please check with the
    artist you're inviting and and use a personal email rather than a band
    email. This address must match the one on their account.""")

    class Meta:
        model=Artist
        fields=("name", "local")

    def save(self, commit = True):
        artist = super().save(commit=False)
        artist.is_temp_artist = True
        if commit:
            artist.save()
        return artist


class ShowFinderForm(forms.Form):
    date = DatePickerField(required=False)
    end_date = DatePickerField(required=False)
    is_date_range = forms.BooleanField(required=False)
    musicbrainz_artists = forms.ModelMultipleChoiceField(
        queryset=MusicBrainzArtist.objects.all(),
        widget=MusicBrainzArtistSearchWidget(max_artists=settings.MAX_USER_ARTISTS),
        required=False,
        label="Sounds like",
        help_text="""We'll recommend some concerts based on the artists you
        select here. Leave blank to get a randomly sorted list.""",
    )
    concert_tags = forms.MultipleChoiceField(
        choices=ConcertTags,
        widget=forms.CheckboxSelectMultiple(attrs={
            "@click": "$dispatch('widget-update')",
            "class": "accent-clickable",
        }),
        required=False,
        label="Categories",
        help_text="Leave blank to include all show categories.",
    )

    def clean(self):
        cleaned_data = super().clean() or {}
        today = timezone_today()

        date = cleaned_data.get("date")
        if (not date) or date < today:
            cleaned_data['date'] = today

        if cleaned_data.get('is_date_range'):
            end_date = cleaned_data.get("end_date")
            if (not end_date) or end_date < cleaned_data['date']:
                cleaned_data['end_date'] = cleaned_data['date']
            elif cleaned_data['end_date'] - cleaned_data['date'] > timedelta(settings.MAX_DATE_RANGE):
                self.add_error('date',
                    "Max date range is " + str(settings.MAX_DATE_RANGE) + " days."
                )

        return cleaned_data


class ContactForm(DefaultStylingForm):
    class Types(models.TextChoices):
        HELP = "hlp", "Tech support/help"
        CONTACT_MOD = "mod", "Moderator question"
        FEATURE_REQUEST = "ftr", "Feature request"
        REPORT_BUG = "bug", "Bug report"
        OTHER = "oth", "Other"

    email = forms.EmailField(max_length=100, label="Your email")
    type = forms.ChoiceField(choices=Types, widget=StyledSelect)
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea,
                              help_text="Please include as much detail as possible for the quickest help.")
    captcha = CaptchaField()

    def clean_subject(self):
        data = self.cleaned_data["subject"]
        return ' '.join(data.splitlines()) # Email subjects can't have \n or \r


class ModDailyDigestForm(forms.Form):
    date = DatePickerField(widget=DatePickerWidget(allow_past_or_future=-1))

    def clean_date(self):
        date = self.cleaned_data['date']
        today = timezone_today()
        if date > today:
            self.add_error('date',
                "No data for future dates."
                )
        return date
