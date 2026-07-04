function localISO(date) {
    const offsetMs = date.getTimezoneOffset() * 60 * 1000;
    const dateLocal = new Date(date.getTime() - offsetMs);
    const iso = dateLocal.toISOString();
    return iso.slice(0, 10);
}

// Allows direct comparison of date objects by standardizing to noon local time
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date#date_time_string_format
function justDate(year, month, day) {
    return new Date(year, month, day, 12, 0, 0, 0);
}

function justDateISO(isoDateString) {
    return new Date(`${isoDateString}T12:00:00`);
}

function justDateToday() {
    today = new Date();
    return justDate(today.getFullYear(), today.getMonth(), today.getDate());
}

function datesAreEqual(date1, date2) {
    if (!date1 || !date2) return false;
    return date1.getTime() === date2.getTime();
}
