// OneMap address search, as in the Week 7 lab. The search endpoint does not need a token.
// input: text box, list: <ul> for the results, onPick(result) runs when a result is chosen.
// Each result has ADDRESS, POSTAL, LATITUDE and LONGITUDE.
function addSearch(input, list, onPick) {
    var timer;
    input.addEventListener('input', function () {
        clearTimeout(timer);
        // OneMap does not match the "Blk" prefix that residents often type, so it is removed
        var q = input.value.trim().replace(/^(blk|block)\.?\s+/i, '');
        if (q.length < 3) { list.style.display = 'none'; return; }
        timer = setTimeout(function () {
            var url = 'https://www.onemap.gov.sg/api/common/elastic/search?searchVal=' + encodeURIComponent(q) +
                '&returnGeom=Y&getAddrDetails=Y&pageNum=1';
            fetch(url).then(function (r) { return r.json(); }).then(function (data) {
                list.innerHTML = '';
                data.results.slice(0, 8).forEach(function (r) {
                    var li = document.createElement('li');
                    li.innerText = r.ADDRESS;
                    li.onclick = function () {
                        list.style.display = 'none';
                        input.value = r.ADDRESS;
                        onPick(r);
                    };
                    list.appendChild(li);
                });
                list.style.display = data.results.length ? 'block' : 'none';
            }).catch(function () { list.style.display = 'none'; });
        }, 300);
    });
}
