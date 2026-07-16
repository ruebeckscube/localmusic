function modal_popup_data(show_initial=false) {
  return {
    show_modal: show_initial,
    success_text: "",

    open_modal() {
      this.show_modal = true;
      this.success_text = "";
    },

    close_modal() {
      this.show_modal = false;
    },

    on_successful_create(event) {
      this.success_text = event.detail.success_text || "";
      this.close_modal();
    }
  }
}
