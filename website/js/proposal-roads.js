/* Visible-area road loading, canonical ID lookup and public API privacy checks. */
var ProposalRoads = (function () {
    'use strict';
    function collection(features) { return { type: 'FeatureCollection', features: features }; }
    function overlap(a, b) { return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1]; }
    function escape(value) { return String(value).replace(/[&<>"']/g, function (s) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s]; }); }
    function distance(value) { return typeof value === 'number' && isFinite(value) && value >= 0 ? Math.round(value) + ' m' : 'Not available'; }
    function Store(base, options) {
        this.base = base.replace(/\/?$/, '/'); this.options = options || {}; this.cache = new Map(); this.pending = new Map();
        this.active = 0; this.queue = []; this.metrics = { requests: 0, tiles: 0, bytes: 0, peakConcurrent: 0, sourceUpdates: 0 }; this.generation = 0;
    }
    Store.prototype.request = function (path) {
        var self = this;
        if (self.cache.has(path)) { var v = self.cache.get(path); self.cache.delete(path); self.cache.set(path, v); return Promise.resolve(v); }
        if (self.pending.has(path)) { return self.pending.get(path); }
        var promise = new Promise(function (resolve, reject) {
            function run() {
                self.active++; self.metrics.peakConcurrent = Math.max(self.metrics.peakConcurrent, self.active); self.metrics.requests++;
                fetch(self.base + path).then(function (r) {
                    if (!r.ok) { throw new Error('Road data unavailable'); }
                    if (/\.gz$/.test(path)) {
                        return new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text();
                    }
                    return r.text();
                })
                    .then(function (text) {
                        var data = JSON.parse(text); self.metrics.bytes += text.length; self.cache.set(path, data);
                        while (self.cache.size > 48) { self.cache.delete(self.cache.keys().next().value); }
                        resolve(data);
                    }).catch(reject).finally(function () {
                        self.active--; self.pending.delete(path); if (self.queue.length) { self.queue.shift()(); }
                    });
            }
            if (self.active < 4) { run(); } else { self.queue.push(run); }
        });
        self.pending.set(path, promise); return promise;
    };
    Store.prototype.init = function () {
        var self = this;
        if (!self.ready) {
            self.ready = self.request('manifest.json').then(function (manifest) {
                if (manifest.schema_version !== 1 || !Number.isSafeInteger(manifest.total_count) || manifest.total_count < 1 ||
                    manifest.existing_count + manifest.added_count !== manifest.total_count || manifest.registry_block_size !== 128 ||
                    (typeof SITE !== 'undefined' && SITE.proposalNetworkVersion && manifest.version !== SITE.proposalNetworkVersion)) { throw new Error('Road data version mismatch'); }
                self.manifest = manifest; return manifest;
            }).catch(function (error) { self.ready = null; throw error; });
        }
        return self.ready;
    };
    Store.prototype.area = function (bounds, options) {
        var self = this, displayOnly = !!(options && options.displayOnly), keys;
        return self.init().then(function (manifest) {
            var tiles = manifest.tiles.filter(function (t) { return overlap(t.bbox, bounds); });
            // A huge viewport at an anomalous zoom must not become an island download.
            if (tiles.length > 16) { throw new Error('Zoom in further to load proposal roads'); }
            keys = tiles.map(function (t) { return t.key; }).sort().join('|');
            self.metrics.tiles += tiles.length;
            return Promise.all(tiles.map(function (t) {
                return Promise.all([self.request(t.url), displayOnly ? null : self.request(t.guard_url)]);
            }));
        }).then(function (sets) {
            var features = new Map(), guards = new Map();
            sets.forEach(function (set) {
                set[0].features.forEach(function (f) { features.set(f.properties.seg_id, f); });
                if (set[1]) { set[1].features.forEach(function (f) { guards.set(f.id, f); }); }
            });
            // Display-only data must never be mistaken for a checked selection.
            // Normal area() calls still require every guard request to succeed.
            return { features: Array.from(features.values()), guards: displayOnly ? null : Array.from(guards.values()),
                guardsReady: !displayOnly, tileKey: keys };
        });
    };
    Store.prototype.feature = function (id) {
        var self = this;
        if (typeof id !== 'number' && !(typeof id === 'string' && /^(0|[1-9][0-9]*)$/.test(id))) {
            return Promise.reject(new Error('Invalid road identifier'));
        }
        id = Number(id);
        if (!Number.isSafeInteger(id) || id < 0) { return Promise.reject(new Error('Invalid road identifier')); }
        return self.init().then(function (manifest) {
            var block = String(Math.floor(id / manifest.registry_block_size));
            if (!manifest.registry_blocks[block]) { throw new Error('Road not found'); }
            return self.request('registry/' + block + (manifest.registry_suffix || '.json'));
        }).then(function (block) {
            if (block.version !== self.manifest.version || !block.segments[String(id)]) { throw new Error('Road not found'); }
            var row = block.segments[String(id)];
            return { type: 'Feature', id: id, geometry: row.g, properties: row.p || { seg_id: id, dist_m: row.d } };
        });
    };
    Store.prototype.attach = function (map, source, status) {
        var self = this, timer = null;
        function send(data, key) {
            if (self.displayKey === key) { return; }
            map.getSource(source).setData(collection(data)); self.displayKey = key; self.metrics.sourceUpdates++;
            if (typeof performance !== 'undefined') { self.metrics.lastDisplayUpdateMs = performance.now(); }
        }
        function update() {
            var token = ++self.generation;
            if (map.getZoom() < 16) { send([], 'below-zoom'); self.current = null; if (status) { status('zoom'); } return; }
            var b = map.getBounds();
            if (status) { status('loading'); }
            self.area([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], { displayOnly: true }).then(function (data) {
                if (token !== self.generation) { return; }
                self.current = data; send(data.features, data.tileKey); if (status) { status('ready'); }
            }).catch(function () {
                if (token !== self.generation) { return; }
                self.current = null; send([], 'error'); if (status) { status('error'); }
            });
        }
        // Refresh during a long fly-to, instead of waiting for its final frame.
        // The tile key prevents repeated GeoJSON worker uploads on small pans.
        map.on('move', function () { if (timer === null) { timer = setTimeout(function () { timer = null; update(); }, 100); } });
        map.on('moveend', function () { if (timer !== null) { clearTimeout(timer); timer = null; } update(); }); update();
        // Manifest only at startup; no tile downloads below the selection zoom.
        self.init().catch(function () { if (status) { status('error'); } });
    };
    function compatible(response) {
        return response && response.api_version === 'proposal-api-v2' && response.publication_min >= 3 &&
            response.line_min >= 3 && response.registry_version === SITE.proposalNetworkVersion;
    }
    function publicSegments(response) {
        if (!compatible(response)) { throw new Error('The proposal service is not ready for this road network'); }
        return (response.segments || []).filter(function (s) {
            return s.reviewed === true && Number.isSafeInteger(s.seg_id) && s.count >= 3;
        });
    }
    function getPublic(url, view, signal) {
        return fetch(url + (url.indexOf('?') < 0 ? '?' : '&') + 'view=' + view, { signal: signal }).then(function (r) {
            if (!r.ok) { throw new Error('Proposal service unavailable'); } return r.json();
        }).then(function (res) { if (!compatible(res)) { throw new Error('Proposal service version mismatch'); } return res; });
    }
    function requireService(url, signal) {
        return getPublic(url, 'capabilities', signal).then(function (res) {
            if (!res.ok || res.scope !== 'published_only' || res.moderation_required !== true || res.max_crossing_m !== 80) {
                throw new Error('Proposal service is not ready');
            }
            return res;
        });
    }
    return { Store: Store, collection: collection, publicSegments: publicSegments, getPublic: getPublic, requireService: requireService, compatible: compatible,
        distance: distance, escape: escape, overlap: overlap };
}());
if (typeof module !== 'undefined' && module.exports) { module.exports = ProposalRoads; }
