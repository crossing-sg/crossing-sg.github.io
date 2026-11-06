/** Local public-launch source. Do not update an existing live deployment to test.
 * Required files: Code.gs, RegistryConfig.gs, RoadGeometry.gs,
 * ValidationConfig.gs and MultiRoad.gs. No live deployment is changed here.
 * Set PROPOSAL_SPREADSHEET_ID and both HTTPS asset bases in Script Properties.
 * setup() appends schema columns without deleting old rows. All new rows await review.
 */
// Demo publication: display a road and an approximate line from its first accepted proposal.
var MIN_PROPOSALS = 1;
var LINE_MIN = 1;
var API_VERSION = 'proposal-api-v2';
var TYPES = ['Zebra crossing', 'Signalised crossing', 'Overhead bridge with lift', 'Underpass', 'Not sure'];
var REASONS = ['Nearest crossing is too far', 'Stairs at the overhead bridge', 'Long wait at the lights', 'Existing crossing is not on the way', 'Other'];
var PROPOSAL_HEADERS = ['received','seg_id','dist_m','a_lng','a_lat','b_lng','b_lat','type','reason','story','story_status','status',
  'schema_version','registry_version','request_id','review_status',
  'validation_version','validation_status','validation_review_status','validation_review_note','validation_review_hash',
  'segment_ids_json','crossings_json','ingestion_status','payload_hash','review_reasons_json'];
var SUPPORT_HEADERS = ['received','seg_id','status','request_id'];
var roadRuntime = {};

function setup() {
  var ss = proposalSpreadsheet();
  [['proposals',PROPOSAL_HEADERS],['support',SUPPORT_HEADERS],['proposal_segments',MEMBERSHIP_HEADERS]].forEach(function (entry) {
    var sh = ss.getSheetByName(entry[0]) || ss.insertSheet(entry[0]);
    if (typeof sh.getMaxColumns === 'function' && sh.getMaxColumns() < entry[1].length) {
      sh.insertColumnsAfter(sh.getMaxColumns(), entry[1].length - sh.getMaxColumns());
    }
    if (sh.getLastRow()) {
      var old = sh.getRange(1,1,1,entry[1].length).getValues()[0];
      old.forEach(function (h,i) { if (h && h !== entry[1][i]) { throw new Error('Unexpected header; review schema before setup'); } });
    }
    sh.getRange(1,1,1,entry[1].length).setValues([entry[1]]).setFontWeight('bold'); sh.setFrozenRows(1);
  });
  var status = SpreadsheetApp.newDataValidation().requireValueInList(['pending','ok','rejected'],true).build();
  var review = SpreadsheetApp.newDataValidation().requireValueInList(['pending','approved','rejected'],true).build();
  sheet('proposals').getRange('L2:L').setDataValidation(status);
  sheet('proposals').getRange('K2:K').setDataValidation(review);
  sheet('proposals').getRange('P2:P').setDataValidation(review);
  sheet('support').getRange('C2:C').setDataValidation(status);
}

function policy() {
  if (!Number.isSafeInteger(MIN_PROPOSALS) || MIN_PROPOSALS < 1 || !Number.isSafeInteger(LINE_MIN) || LINE_MIN < 1) { throw new Error('publication_policy'); }
}
function envelope(obj) {
  obj.api_version = API_VERSION; obj.registry_version = ROAD_REGISTRY_VERSION;
  obj.publication_min = MIN_PROPOSALS; obj.line_min = LINE_MIN; return obj;
}
function json(obj) { return ContentService.createTextOutput(JSON.stringify(envelope(obj))).setMimeType(ContentService.MimeType.JSON); }
function doPost(e) {
  var lock = LockService.getScriptLock(), locked = false; roadRuntime = {};
  try {
    policy();
    if (!e || !e.postData || typeof e.postData.contents !== 'string') { return json({ok:false,error:'request'}); }
    var data = JSON.parse(e.postData.contents);
    if (!data || typeof data !== 'object' || Array.isArray(data)) { return json({ok:false,error:'request'}); }
    if (data.website) { return json({ok:true,received:true,status:'pending'}); }
    lock.waitLock(10000); locked = true;
    if (data.kind === 'proposal') { return json(saveProposal(data)); }
    if (data.kind === 'support') { return json(saveSupport(data)); }
    return json({ok:false,error:'request'});
  } catch (err) { return json({ok:false,error:'service_unavailable'}); }
  finally { if (locked) { lock.releaseLock(); } }
}
function doGet(e) {
  roadRuntime = {};
  try {
    policy(); var view = e && e.parameter && e.parameter.view || 'segments';
    if (view === 'capabilities') { return json(capabilities()); }
    if (['segments','summary','csv'].indexOf(view)<0) { return json({ok:false,error:'view'}); }
    var publication = publicationState(), list = publication.segments;
    if (view === 'csv') { return ContentService.createTextOutput(toCsv(list)).setMimeType(ContentService.MimeType.CSV); }
    if (view === 'summary') { return json(publication.summary); }
    if (view === 'segments') { return json({ok:true,segments:list,crossings:publication.crossings,summary:publication.summary}); }
    return json({ok:false,error:'view'});
  } catch (err) { return json({ok:false,error:'service_unavailable'}); }
}

function digest(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,text,Utilities.Charset.UTF_8).map(function (n) {
    return ('0' + ((n + 256) % 256).toString(16)).slice(-2);
  }).join('');
}
function staticJson(path, expected) {
  var key = 'roads:' + expected;
  if (roadRuntime[key]) { return roadRuntime[key]; }
  var cache = CacheService.getScriptCache(), text = cache.get(key);
  if (!text) {
    var base = PropertiesService.getScriptProperties().getProperty('PROPOSAL_DATA_BASE_URL') || '';
    if (!/^https:\/\/[a-zA-Z0-9.-]+\/[a-zA-Z0-9_./-]*proposal-roads\/?$/.test(base)) { throw new Error('registry_config'); }
    var response = UrlFetchApp.fetch(base.replace(/\/$/,'') + '/' + path,{muteHttpExceptions:true,validateHttpsCertificates:true});
    if (response.getResponseCode() !== 200) { throw new Error('registry_unavailable'); }
    text = /\.gz$/.test(path) ? Utilities.ungzip(response.getBlob()).getDataAsString('UTF-8') : response.getContentText('UTF-8');
  }
  if (digest(text) !== expected) { throw new Error('registry_integrity'); }
  // Apps Script cache values have a 100 KB limit; large tiles remain uncached.
  if (Utilities.newBlob(text).getBytes().length < 90000) { cache.put(key,text,21600); }
  var value = JSON.parse(text); roadRuntime[key] = value; return value;
}
function manifest() {
  var m = staticJson('manifest.json',ROAD_MANIFEST_SHA256);
  if (m.version !== ROAD_REGISTRY_VERSION || !Number.isSafeInteger(m.total_count) || m.total_count < 1 ||
      m.existing_count + m.added_count !== m.total_count || m.registry_block_size !== 128) { throw new Error('registry_version'); }
  return m;
}
function road(id) {
  if (!Number.isSafeInteger(id) || id < 0) { return null; }
  var m = manifest(), block = String(Math.floor(id / m.registry_block_size));
  if (!m.registry_blocks[block]) { return null; }
  var data = staticJson('registry/' + block + (m.registry_suffix || '.json'),m.registry_blocks[block]);
  if (data.version !== ROAD_REGISTRY_VERSION) { throw new Error('registry_version'); }
  return data.segments[String(id)] || null;
}
function neighborhood(a,b) {
  var bounds = [Math.min(a[0],b[0])-.00005,Math.min(a[1],b[1])-.00005,Math.max(a[0],b[0])+.00005,Math.max(a[1],b[1])+.00005];
  var m = manifest(), features = {}, guards = {};
  m.tiles.filter(function (t) { var q=t.bbox; return q[0]<=bounds[2] && q[2]>=bounds[0] && q[1]<=bounds[3] && q[3]>=bounds[1]; }).forEach(function (t) {
    staticJson(t.url,t.sha256).features.forEach(function (f) { features[f.properties.seg_id]=f; });
    staticJson(t.guard_url,t.guard_sha256).features.forEach(function (f) { guards[f.id]=f; });
  });
  return {features:Object.keys(features).map(function (k) { return features[k]; }),guards:Object.keys(guards).map(function (k) { return guards[k]; })};
}
function validRequestId(value) { return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value); }
function acknowledgement() { return {ok:true,received:true,status:'pending'}; }
function saveProposal(d) {
  if (multiRoadEnabled()) { return saveProposalRecord(d); }
  if (d.segment_ids !== undefined) { return {ok:false,error:'unsupported_schema'}; }
  // Disabling array ingestion must not turn new scalar submissions into trusted
  // historical rows or bypass the candidate's unknown-grade review requirement.
  if (validationPolicyApplies()) { return saveProposalRecord(d); }
  return saveLegacyProposal(d);
}
function saveLegacyProposal(d) {
  if (d.registry_version !== ROAD_REGISTRY_VERSION) { return {ok:false,error:'registry_version'}; }
  var canonical = road(d.seg_id);
  if (!canonical) { return {ok:false,error:'segment'}; }
  if (!validRequestId(d.request_id)) { return {ok:false,error:'request_id'}; }
  if (TYPES.indexOf(d.type)<0 || REASONS.indexOf(d.reason)<0) { return {ok:false,error:'choice'}; }
  if (!RoadGeometry.validPoint(d.a) || !RoadGeometry.validPoint(d.b)) { return {ok:false,error:'location'}; }
  var a=d.a.map(round6), b=d.b.map(round6), nearby=neighborhood(a,b);
  var match=RoadGeometry.choose(a,b,nearby.features,nearby.guards);
  if (!match.ok || match.feature.properties.seg_id !== d.seg_id) { return {ok:false,error:match.reason || 'segment_mismatch'}; }
  var old=rows('proposals',PROPOSAL_HEADERS).filter(function (r) { return r.request_id===d.request_id; });
  if (old.length) {
    if (old[0].seg_id!==d.seg_id) { return {ok:false,error:'request_id'}; }
    return acknowledgement(); // no count/hidden activity is disclosed, including on retries
  }
  if (d.story !== undefined && typeof d.story !== 'string') { return {ok:false,error:'story'}; }
  var story=String(d.story || '').slice(0,300).trim();
  // Canonical ordering prevents reversed A/B submissions cancelling the aggregate.
  if (a[0]>b[0] || (a[0]===b[0] && a[1]>b[1])) { var swap=a;a=b;b=swap; }
  requireHeaders('proposals',PROPOSAL_HEADERS);
  sheet('proposals').appendRow(sheetValues([new Date(),d.seg_id,canonical.d===null?'':canonical.d,a[0],a[1],b[0],b[1],d.type,d.reason,
    story,story?'pending':'','pending',API_VERSION,ROAD_REGISTRY_VERSION,d.request_id,'pending']));
  return acknowledgement();
}
function saveSupport(d) {
  if (d.registry_version!==ROAD_REGISTRY_VERSION || !validRequestId(d.request_id) || !road(d.seg_id)) { return {ok:false,error:'unavailable'}; }
  if (!segments().some(function (s) { return s.seg_id===d.seg_id; })) { return {ok:false,error:'unavailable'}; }
  requireHeaders('support',SUPPORT_HEADERS);
  if (!rows('support',SUPPORT_HEADERS).some(function (r) { return r.request_id===d.request_id; })) {
    sheet('support').appendRow(sheetValues([new Date(),d.seg_id,'ok',d.request_id]));
  }
  return {ok:true};
}

function approvedRows() { return approvedParents(); }
function segments() { return publicationState().segments; }
function summary() { return publicationState().summary; }
function toCsv(list) {
  var head=['seg_id','proposals','support','nearest_crossing_m','most_requested_type','most_common_reason'];
  return [head.join(',')].concat(list.map(function (s) {
    return [s.seg_id,s.count,s.support,s.dist_m,s.top_type,s.top_reason].map(function (v) {
      return '"'+String(v===null || v===undefined?'':v).replace(/"/g,'""')+'"';
    }).join(',');
  })).join('\n');
}
// Sheets removes this input escape when it stores a text value. Apply it at
// EVERY data write, including read-modify-write updates; hash logical text,
// never the input escape. Numbers and Dates retain their native cell types.
function sheetValues(values) { return values.map(function(v){return typeof v==='string'&&v!==''?"'"+v:v;}); }
function rows(name,headers) {
  var sh=sheet(name),last=sh.getLastRow(); if (last<2) { return []; }
  var actual=sh.getRange(1,1,1,headers.length).getValues()[0];
  return sh.getRange(2,1,last-1,headers.length).getValues().map(function (values,valuesIndex) {
    var row={_row:valuesIndex+2};headers.forEach(function (h) { var index=actual.indexOf(h);row[h]=index<0?'':values[index]; });
    row.seg_id=row.seg_id===''?NaN:Number(row.seg_id);return row;
  });
}
function requireHeaders(name,headers) {
  var actual=sheet(name).getRange(1,1,1,headers.length).getValues()[0];
  if (actual.join('|')!==headers.join('|')) { throw new Error('setup_required'); }
}
function proposalSpreadsheet() {
  var id = PropertiesService.getScriptProperties().getProperty('PROPOSAL_SPREADSHEET_ID');
  // Web apps have no active spreadsheet. Keep the bound editor fallback for local setup.
  var spreadsheet = id ? SpreadsheetApp.openById(id) : SpreadsheetApp.getActiveSpreadsheet();
  if (!spreadsheet) { throw new Error('spreadsheet_config'); }
  return spreadsheet;
}
function sheet(name) { var sh=proposalSpreadsheet().getSheetByName(name);if (!sh) { throw new Error('setup_required'); }return sh; }
function top(counts) { var result={key:'',n:0};Object.keys(counts).sort().forEach(function (k) { if (counts[k]>result.n) { result={key:k,n:counts[k]}; } });return result; }
function round6(x) { return Math.round(Number(x)*1e6)/1e6; }
function round4(x) { return Math.round(Number(x)*1e4)/1e4; }
function round3(x) { return Math.round(Number(x)*1e3)/1e3; }
