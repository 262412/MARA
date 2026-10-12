
function(_, __) {
    api_key = getStorage('google_api_key', '');
    return [api_key, _];
}
