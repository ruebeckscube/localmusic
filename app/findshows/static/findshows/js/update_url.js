function update_url(pathInfo, expectedRequestPath, finalBasePath) {
    if (pathInfo.requestPath !== expectedRequestPath) return;

    params = new URLSearchParams(
        pathInfo.finalRequestPath.slice(pathInfo.requestPath.length)
    );
    params.delete('mb_search');
    if (params.get('is_date_range') !== 'true') {
        params.delete('is_date_range');
        params.delete('end_date');
    }

    window.history.replaceState('', '', finalBasePath + '?' + params.toString());
}
