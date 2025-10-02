function venue_picker_data(initial_venue_id, initial_venue_name, initial_venue_is_verified, initial_venue_declined_listing) {
  return {
    search_text: initial_venue_name,
    show_search: false,

    selected_venue_name: initial_venue_name,
    selected_venue_id: initial_venue_id,
    selected_venue_is_verified: initial_venue_is_verified,
    selected_venue_declined_listing: initial_venue_declined_listing,

    created_venue_name: '',
    created_venue_id: '',

    open_dropdown() {
      if (this.show_search) return;
      this.show_search = true;
    },

    close_dropdown(focusAfter) {
      if (! this.show_search) return;
      this.show_search = false;
      if (this.selected_venue_name) {
        this.search_text = this.selected_venue_name;
      }
      focusAfter && focusAfter.focus();
    },

    select_venue(venue_name, venue_id, is_verified, declined_listing) {
      this.search_text = venue_name;
      this.selected_venue_name = venue_name;
      this.selected_venue_id = venue_id;
      this.selected_venue_is_verified = is_verified;
      this.selected_venue_declined_listing = declined_listing;
    },

    on_venue_create(event) {
      this.select_venue(event.detail.created_record_name, event.detail.created_record_id)
    },

  }
}
