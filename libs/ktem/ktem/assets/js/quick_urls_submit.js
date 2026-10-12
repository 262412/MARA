
function() {
    let urlInput = document.querySelector("#quick-url-demo textarea");
    urlInput.dispatchEvent(new KeyboardEvent('keypress', {'key': 'Enter'}));
}
