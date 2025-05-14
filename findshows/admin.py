from django.contrib import admin

from .models import Artist, ArtistLinkingInfo, CustomText, MusicBrainzArtist, UserProfile, Venue, Concert, SetOrder

class SetOrderInline(admin.TabularInline):
    model = SetOrder
    extra = 1 # how many rows to show
    autocomplete_fields = ("artist",)

class ConcertAdmin(admin.ModelAdmin):
    inlines = (SetOrderInline,)
    autocomplete_fields = ('venue',)

class VenueAdmin(admin.ModelAdmin):
    search_fields = ('name',)

class UserProfileAdmin(admin.ModelAdmin):
    readonly_fields = ('favorite_musicbrainz_artists',)
    autocomplete_fields = ('followed_artists', 'managed_artists')

class ArtistAdmin(admin.ModelAdmin):
    readonly_fields=('similar_musicbrainz_artists',)
    search_fields=('name',)

class MusicBrainzArtistAdmin(admin.ModelAdmin):
    readonly_fields=('mbid', 'name')

admin.site.register(Concert, ConcertAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Artist, ArtistAdmin)
admin.site.register(Venue, VenueAdmin)
admin.site.register(MusicBrainzArtist, MusicBrainzArtistAdmin)
admin.site.register(ArtistLinkingInfo)
admin.site.register(CustomText)
# Register your models here.
