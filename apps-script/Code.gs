/**
 * Backend for "Where residents want to cross the road".
 * Bound to the project Google Sheet (Extensions > Apps Script). Deploy as a web app:
 * Execute as: Me. Who has access: Anyone.
 *
 * POST (from the website, sent as text/plain JSON)
 *   { kind: 'proposal', seg_id, dist_m, a: [lng, lat], b: [lng, lat], type, reason, story, website }
 *   { kind: 'support', seg_id }
 * GET
 *   ?view=segments  segments with 3 or more proposals, aggregated, no individual points
 *   ?view=summary   totals for the cards on the home page
 *   ?view=csv       aggregated table for download
 */

var MIN_PROPOSALS = 3;
var TYPES = ['Zebra crossing', 'Signalised crossing', 'Overhead bridge with lift', 'Underpass', 'Not sure'];
var REASONS = ['Nearest crossing is too far', 'Stairs at the overhead bridge', 'Long wait at the lights',
  'Existing crossing is not on the way', 'Other'];
var SG_BOUNDS = { west: 103.59, east: 104.10, south: 1.15, north: 1.48 };

var PROPOSAL_HEADERS = ['received', 'seg_id', 'dist_m', 'a_lng', 'a_lat', 'b_lng', 'b_lat',
  'type', 'reason', 'story', 'story_status', 'status'];
var SUPPORT_HEADERS = ['received', 'seg_id', 'status'];

/** Run once from the editor to create the two tabs with their headers. */
function setup() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  [['proposals', PROPOSAL_HEADERS], ['support', SUPPORT_HEADERS]].forEach(function (t) {
    var sh = ss.getSheetByName(t[0]) || ss.insertSheet(t[0]);
    sh.getRange(1, 1, 1, t[1].length).setValues([t[1]]).setFontWeight('bold');
    sh.setFrozenRows(1);
  });
  var proposals = ss.getSheetByName('proposals');
  var statusRule = SpreadsheetApp.newDataValidation().requireValueInList(['ok', 'rejected'], true).build();
  var storyRule = SpreadsheetApp.newDataValidation().requireValueInList(['', 'pending', 'approved', 'rejected'], true).build();
  proposals.getRange('L2:L').setDataValidation(statusRule);
  proposals.getRange('K2:K').setDataValidation(storyRule);
  ss.getSheetByName('support').getRange('C2:C').setDataValidation(statusRule);
}

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    var data = JSON.parse(e.postData.contents);
    // Hidden field that only automated spam fills in: answer as if saved, store nothing
    if (data.website) { return json({ ok: true, count: 0 }); }
    lock.waitLock(10000);
    if (data.kind === 'proposal') { return json(saveProposal(data)); }
    if (data.kind === 'support') { return json(saveSupport(data)); }
    return json({ ok: false, error: 'unknown kind' });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

function saveProposal(d) {
  var segId = Number(d.seg_id);
  if (!isFinite(segId) || segId < 0) { return { ok: false, error: 'segment' }; }
  if (TYPES.indexOf(d.type) < 0 || REASONS.indexOf(d.reason) < 0) { return { ok: false, error: 'choice' }; }
  if (!inSingapore(d.a) || !inSingapore(d.b)) { return { ok: false, error: 'location' }; }
  var story = String(d.story || '').slice(0, 300).trim();
  var sh = sheet('proposals');
  sh.appendRow([new Date(), segId, Number(d.dist_m) || '', round4(d.a[0]), round4(d.a[1]), round4(d.b[0]), round4(d.b[1]),
    d.type, d.reason, story, story ? 'pending' : '', 'ok']);
  var count = proposalRows().filter(function (r) { return r.seg_id === segId; }).length;
  return { ok: true, count: count, road: 'Road segment ' + segId };
}

function saveSupport(d) {
  var segId = Number(d.seg_id);
  if (!isFinite(segId) || segId < 0) { return { ok: false, error: 'segment' }; }
  sheet('support').appendRow([new Date(), segId, 'ok']);
  return { ok: true };
}

function doGet(e) {
  var view = (e.parameter && e.parameter.view) || 'segments';
  if (view === 'summary') { return json(summary()); }
  if (view === 'csv') {
    return ContentService.createTextOutput(toCsv(segments())).setMimeType(ContentService.MimeType.CSV);
  }
  return json({ segments: segments() });
}

/** Segments with at least MIN_PROPOSALS proposals. Individual points are averaged, never returned. */
function segments() {
  var groups = {};
  proposalRows().forEach(function (r) {
    var g = groups[r.seg_id] || (groups[r.seg_id] = { rows: [], types: {}, reasons: {} });
    g.rows.push(r);
    g.types[r.type] = (g.types[r.type] || 0) + 1;
    g.reasons[r.reason] = (g.reasons[r.reason] || 0) + 1;
  });
  var support = {};
  rows('support', SUPPORT_HEADERS).forEach(function (r) {
    if (r.status !== 'rejected') { support[r.seg_id] = (support[r.seg_id] || 0) + 1; }
  });
  return Object.keys(groups).map(Number).filter(function (id) {
    return groups[id].rows.length >= MIN_PROPOSALS;
  }).map(function (id) {
    var g = groups[id], n = g.rows.length;
    var mean = function (k) { return round4(g.rows.reduce(function (s, r) { return s + Number(r[k]); }, 0) / n); };
    var topType = top(g.types), topReason = top(g.reasons);
    return {
      seg_id: id,
      road: 'Road segment ' + id,
      count: n,
      support: support[id] || 0,
      dist_m: g.rows[0].dist_m,
      top_type: topType.key + ' (' + topType.n + ' of ' + n + ')',
      top_reason: topReason.key + ' (' + topReason.n + ' of ' + n + ')',
      line: [[mean('a_lng'), mean('a_lat')], [mean('b_lng'), mean('b_lat')]]
    };
  });
}

function summary() {
  var list = proposalRows();
  var last = list.length ? list[list.length - 1].received : null;
  return {
    proposals: list.length,
    segments: segments().length,
    lastUpdated: last ? Utilities.formatDate(new Date(last), 'Asia/Singapore', 'd MMM yyyy') : '-'
  };
}

function toCsv(list) {
  var head = ['seg_id', 'proposals', 'support', 'nearest_crossing_m', 'most_requested_type', 'most_common_reason'];
  var body = list.map(function (s) {
    return [s.seg_id, s.count, s.support, s.dist_m, s.top_type, s.top_reason].map(function (v) {
      return '"' + String(v).replace(/"/g, '""') + '"';
    }).join(',');
  });
  return [head.join(',')].concat(body).join('\n');
}

// Helpers
function proposalRows() {
  return rows('proposals', PROPOSAL_HEADERS).filter(function (r) { return r.status !== 'rejected'; });
}

function rows(name, headers) {
  var sh = sheet(name), last = sh.getLastRow();
  if (last < 2) { return []; }
  return sh.getRange(2, 1, last - 1, headers.length).getValues().map(function (v) {
    var o = {};
    headers.forEach(function (h, i) { o[h] = v[i]; });
    o.seg_id = Number(o.seg_id);
    return o;
  });
}

function sheet(name) { return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(name); }

function top(counts) {
  var best = { key: '', n: 0 };
  Object.keys(counts).forEach(function (k) { if (counts[k] > best.n) { best = { key: k, n: counts[k] }; } });
  return best;
}

function inSingapore(p) {
  return Array.isArray(p) && p[0] > SG_BOUNDS.west && p[0] < SG_BOUNDS.east && p[1] > SG_BOUNDS.south && p[1] < SG_BOUNDS.north;
}

function round4(x) { return Math.round(Number(x) * 10000) / 10000; }

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
