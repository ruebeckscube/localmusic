links = document.getElementsByTagName('a')
for (link of links) {
    if ('ed' in link.dataset && 'eu' in link.dataset) {
        link.href = "mailto:" + link.dataset.eu + "@" + link.dataset.ed;
    }
}
