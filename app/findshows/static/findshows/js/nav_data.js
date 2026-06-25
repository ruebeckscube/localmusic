function nav_data() {
    return {
        show_menu: false,
        arrowPress(evt, upOrDown) {
            let el = evt.target;
            let li = el.tag == 'li' ? el : el.closest('menu li');
            if (upOrDown == "up") {
                if (!li) return;
                var newFocus = li.previousElementSibling || li.closest('nav');
            } else if (upOrDown == "down") {
                var newFocus = li ? li.nextElementSibling : el.nextElementSibling;
            }
            if (!newFocus) return;
            newFocus.querySelector('a, button').focus();
        }
    }
}
