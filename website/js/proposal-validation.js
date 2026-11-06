/* Capability-negotiated selection evidence. All assets are pinned and separate from roads. */
var ProposalValidation = (function () {
    'use strict';
    function overlap(a, b) { return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1]; }
    function digest(text) {
        return crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)).then(function (bytes) {
            return Array.from(new Uint8Array(bytes), function (n) { return n.toString(16).padStart(2, '0'); }).join('');
        });
    }
    function Store(config) { this.config = config; this.cache = new Map(); }
    Store.prototype.checked = function (path, hash) {
        var self = this;
        if (!self.cache.has(path)) {
            var promise = fetch(self.config.validationBase + '/' + path).then(function (r) {
                if (!r.ok) { throw new Error('Validation unavailable'); }
                return /\.gz$/.test(path) ? new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text() : r.text();
            }).then(function (text) {
                return digest(text).then(function (actual) { if (actual !== hash) { throw new Error('Validation checksum mismatch'); } return JSON.parse(text); });
            }).catch(function (e) { self.cache.delete(path); throw e; });
            self.cache.set(path, promise);
        }
        return self.cache.get(path);
    };
    Store.prototype.init = function () {
        var self = this;
        return self.checked('manifest.json', self.config.validationManifestSha256).then(function (m) {
            if (m.schema_version !== 1 || m.version !== self.config.validationVersion || m.network_version !== SITE.proposalNetworkVersion ||
                m.network_manifest_sha256 !== self.config.networkManifestSha256 || m.total_count !== self.config.networkTotalCount || m.block_size !== 128) { throw new Error('Validation version mismatch'); }
            return m;
        });
    };
    Store.prototype.context = function (a, b, features) {
        var self = this, raw = RoadGeometry.contacts(a, b, features), ids = Array.from(new Set(raw.contacts.map(function (h) { return h.feature.properties.seg_id; })));
        var bounds = [Math.min(a[0], b[0]) - .00005, Math.min(a[1], b[1]) - .00005, Math.max(a[0], b[0]) + .00005, Math.max(a[1], b[1]) + .00005];
        return self.init().then(function (m) {
            var blocks = Array.from(new Set(ids.map(function (id) { return String(Math.floor(id / 128)); })));
            var tiles = m.tiles.filter(function (t) { return overlap(t.bbox, bounds); });
            return Promise.all([
                Promise.all(blocks.map(function (block) { if (!m.blocks[block]) { throw new Error('Missing validation block'); } return self.checked('records/' + block + '.json.gz', m.blocks[block]); })),
                Promise.all(tiles.map(function (t) { return self.checked(t.url, t.sha256); }))
            ]).then(function (sets) {
                var records = {}, guards = new Map();
                sets[0].forEach(function (block) { if (block.policy !== m.policy) { throw new Error('Validation policy mismatch'); } Object.assign(records, block.records); });
                ids.forEach(function (id) { if (!records[id] || records[id].seg_id !== id) { throw new Error('Missing segment evidence'); } });
                sets[1].forEach(function (tile) { if (tile.policy !== m.policy) { throw new Error('Guard policy mismatch'); } tile.features.forEach(function (f) { guards.set(f.id, f); }); });
                return { ready: true, version: m.version, records: records, guards: Array.from(guards.values()) };
            });
        }).catch(function () { return { ready: false, version: self.config.validationVersion, records: {}, guards: [], error: 'validation_unavailable' }; });
    };
    return { Store: Store, digest: digest };
}());
if (typeof module !== 'undefined' && module.exports) { module.exports = ProposalValidation; }
