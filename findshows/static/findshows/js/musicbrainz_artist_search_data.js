function musicbrainz_artist_search_data(selected_musicbrainz_artists, max_artists) {
  return {
    show_search: false,
    search_text: '',
    selected_musicbrainz_artists: selected_musicbrainz_artists,

    open_dropdown() {
      if (this.show_search) return;
      this.show_search = true;
    },

    close_dropdown(focusAfter) {
      if (! this.show_search) return;
      this.show_search = false;
      focusAfter && focusAfter.focus();
    },

    add_artist(mbid, name) {
      if (this.selected_musicbrainz_artists.length < max_artists && !this.selected_musicbrainz_artists.some(a => a.mbid === mbid)) {
        this.selected_musicbrainz_artists.push({'mbid':mbid, 'name':name});
        this.search_text = '';
      }
      this.$dispatch('widget-update');
    },

    remove_artist(index) {
      this.selected_musicbrainz_artists.splice(index, 1);
      this.$dispatch('widget-update');
    }
  }
}
