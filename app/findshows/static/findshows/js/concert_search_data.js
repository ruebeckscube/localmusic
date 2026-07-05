function concertSearchData(initial_show_end_date) {
    return {
        'show_end_date': initial_show_end_date,
        'show_search_form': true,

        'show_hide_date_range': function (showOrHide, focus_id) {
            this.show_end_date=(showOrHide === 'show');
            this.$nextTick(() => {document.getElementById(focus_id).focus()});
            this.$dispatch('widget-update');
        }
    }
}
