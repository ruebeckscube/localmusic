function arrowPress(evt, upOrDown) {
    let el = evt.target;
    let current_li = el.tag == 'li' ? el : el.closest('menu li');
    if (upOrDown == "up") {
        if (!current_li) return;
        var new_li = current_li.previousElementSibling || current_li.closest('.dropdown-container');
    } else if (upOrDown == "down") {
        var new_li = current_li ? current_li.nextElementSibling : el.nextElementSibling;
    }
    if (!new_li) return;
    new_focus = new_li.querySelector('a, button, input[type="search"]') || new_li.querySelector('li') || new_li;
    new_focus.focus();
}
