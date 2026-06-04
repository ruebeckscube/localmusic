(function () {
    const FLAG = 'iframe[data-play-one-flag]';
    let lastActive = null;

    function reset(iframe) {
        const src = iframe.src;
        iframe.src = '';
        iframe.src = src;
    }

    function check() {
        const selected = document.activeElement;
        if (selected && selected.tagName === 'IFRAME' && selected.matches(FLAG) && selected !== lastActive) {
            if (lastActive) reset(lastActive);
            lastActive = selected;
        }
    }

    setInterval(check, 300);
})();