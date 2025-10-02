function modal_form_data() {
  return {
    show_modal: false,
    show_success: false,

    open_modal() {
      this.show_modal = true;
      this.show_success = false;
    },

    close_modal() {
      this.show_modal = false;
    },

    on_successful_create() {
      this.show_success = true;
      this.close_modal();
    }
  }
}
