/** One parent, unique road memberships, recoverable ingestion. No HTTP moderation. */
var PROPOSAL_SCHEMA = 'proposal-schema-v3';
var MULTI_PROTOCOL = 'proposal-multi-v1';
var MEMBERSHIP_HEADERS = ['request_id','seg_id','crossing_groups_json','registry_version','schema_version'];

function multiRoadEnabled() {
  return PropertiesService.getScriptProperties().getProperty('ENABLE_MULTI_ROAD') === 'true';
}
function validationPolicyApplies() {
  return typeof ROAD_VALIDATION_REGISTRY_VERSION !== 'undefined' && ROAD_REGISTRY_VERSION === ROAD_VALIDATION_REGISTRY_VERSION;
}
function capabilities() {
  var result={ok:true,scope:'published_only',moderation_required:true,max_crossing_m:80,
    legacy_single_road:true,multi_road:multiRoadEnabled(),schema_version:PROPOSAL_SCHEMA};
  if(result.multi_road){
    var m=validationManifest();
    result.multi_schema_version=MULTI_PROTOCOL;
    result.validation={version:m.version,manifest_sha256:ROAD_VALIDATION_MANIFEST_SHA256,
      network_manifest_sha256:ROAD_MANIFEST_SHA256,total_count:manifest().total_count,
      base:PropertiesService.getScriptProperties().getProperty('PROPOSAL_VALIDATION_BASE_URL')};
  }
  return result;
}
function validationJson(path,expected) {
  var key='validation:'+expected;
  if(roadRuntime[key])return roadRuntime[key];
  var base=PropertiesService.getScriptProperties().getProperty('PROPOSAL_VALIDATION_BASE_URL')||'';
  if(!/^https:\/\/[a-zA-Z0-9.-]+\/[a-zA-Z0-9_./-]+\/?$/.test(base)||!/^[-a-zA-Z0-9_./]+$/.test(path)||path.indexOf('..')>=0)throw Error('validation_config');
  var response=UrlFetchApp.fetch(base.replace(/\/$/,'')+'/'+path,{muteHttpExceptions:true,validateHttpsCertificates:true});
  if(response.getResponseCode()!==200)throw Error('validation_unavailable');
  var text=/\.gz$/.test(path)?Utilities.ungzip(response.getBlob()).getDataAsString('UTF-8'):response.getContentText('UTF-8');
  if(digest(text)!==expected)throw Error('validation_integrity');
  var value=JSON.parse(text);roadRuntime[key]=value;return value;
}
function validationManifest() {
  var v=validationJson('manifest.json',ROAD_VALIDATION_MANIFEST_SHA256),m=manifest();
  if(v.version!==ROAD_VALIDATION_VERSION||v.network_version!==ROAD_REGISTRY_VERSION||v.network_manifest_sha256!==ROAD_MANIFEST_SHA256||v.total_count!==m.total_count||v.block_size!==128)throw Error('validation_version');
  return v;
}
function crossingEvidence(a,b,features) {
  try{
    var m=validationManifest(),records={},guards={},raw=RoadGeometry.contacts(a,b,features),blocks={};
    raw.contacts.forEach(function(h){blocks[String(Math.floor(h.feature.properties.seg_id/128))]=true;});
    Object.keys(blocks).forEach(function(k){
      if(!m.blocks[k])throw Error('missing_evidence');
      var block=validationJson('records/'+k+'.json.gz',m.blocks[k]);if(block.policy!==m.policy)throw Error('validation_policy');
      Object.keys(block.records).forEach(function(id){records[id]=block.records[id];});
    });
    raw.contacts.forEach(function(h){var id=h.feature.properties.seg_id;if(!records[id]||records[id].seg_id!==id)throw Error('missing_evidence');});
    var q=[Math.min(a[0],b[0])-.00005,Math.min(a[1],b[1])-.00005,Math.max(a[0],b[0])+.00005,Math.max(a[1],b[1])+.00005];
    m.tiles.filter(function(t){var p=t.bbox;return p[0]<=q[2]&&p[2]>=q[0]&&p[1]<=q[3]&&p[3]>=q[1];}).forEach(function(t){
      var tile=validationJson(t.url,t.sha256);if(tile.policy!==m.policy)throw Error('validation_policy');
      tile.features.forEach(function(f){guards[f.id]=f;});
    });
    return {ready:true,version:m.version,records:records,guards:Object.keys(guards).map(function(k){return guards[k];})};
  }catch(e){return {ready:false,version:ROAD_VALIDATION_VERSION,records:{},guards:[],error:'validation_unavailable'};}
}
function matchAll(a,b) {
  if(!RoadGeometry.validPoint(a)||!RoadGeometry.validPoint(b)||RoadGeometry.metres(a,b)<2||RoadGeometry.metres(a,b)>80)return RoadGeometry.select(a,b,[],{});
  var n=neighborhood(a,b);return RoadGeometry.select(a,b,n.features,crossingEvidence(a,b,n.features));
}
function sortedIds(ids){return ids.slice().sort(function(a,b){return a-b;});}
function sameIds(a,b){return JSON.stringify(a)===JSON.stringify(b);}
function parseArray(value){try{var a=JSON.parse(value);return Array.isArray(a)?a:[];}catch(e){return [];}}
function requestKey(value){var key=String(value||'');return validRequestId(key)?key.toLowerCase():key;}
function parentIdentity(r){return r.request_id?'request:'+requestKey(r.request_id):'legacy-row:'+r._row;}
function parentHash(a,b,ids,crossings,type,reason,story,validationStatus,validationVersion) {
  var reversed=a[0]>b[0]||(a[0]===b[0]&&a[1]>b[1]),length=RoadGeometry.metres(a,b);
  var groups=(reversed?crossings.slice().reverse():crossings).map(function(g){return {position_m:Math.round((reversed?length-g.position_m:g.position_m)*100)/100,segment_ids:sortedIds(g.segment_ids)};});
  return digest(JSON.stringify({a:reversed?b:a,b:reversed?a:b,ids:sortedIds(ids),groups:groups,type:type,reason:reason,story:story,validation_status:validationStatus,validation_version:validationVersion,registry_version:ROAD_REGISTRY_VERSION}));
}
function updateParent(r,patch) {
  var values=sheet('proposals').getRange(r._row,1,1,PROPOSAL_HEADERS.length).getValues()[0];
  Object.keys(patch).forEach(function(k){var i=PROPOSAL_HEADERS.indexOf(k);if(i<0)throw Error('schema');values[i]=patch[k];r[k]=patch[k];});
  sheet('proposals').getRange(r._row,1,1,PROPOSAL_HEADERS.length).setValues([sheetValues(values)]);
}
function storedParentIntact(r,checkSource) {
  try {
    var a=[Number(r.a_lng),Number(r.a_lat)],b=[Number(r.b_lng),Number(r.b_lat)],ids=parseArray(r.segment_ids_json),groups=parseArray(r.crossings_json);
    if(!RoadGeometry.validPoint(a)||!RoadGeometry.validPoint(b)||!ids.length||new Set(ids).size!==ids.length)return false;
    if(parentHash(a,b,ids,groups,r.type,r.reason,r.story,r.validation_status,r.validation_version)!==r.payload_hash)return false;
    if(checkSource){
      var match=matchAll(a,b);
      if(!match.ok||!sameIds(match.segment_ids,ids)||JSON.stringify(match.crossings)!==JSON.stringify(groups)||(r.validation_status==='valid'&&match.status!=='valid'))return false;
      var stored=parseArray(r.review_reasons_json);
      if(match.review_reasons.some(function(reason){return !stored.some(function(s){return s.code===reason.code&&sameIds(s.segment_ids,reason.segment_ids);});}))return false;
    }
    return true;
  }catch(e){return false;}
}
function membershipRows(r){return rows('proposal_segments',MEMBERSHIP_HEADERS).filter(function(x){return requestKey(x.request_id)===requestKey(r.request_id);});}
function expectedMemberships(r) {
  var groups=parseArray(r.crossings_json),ids=parseArray(r.segment_ids_json);
  return ids.map(function(id){return {request_id:r.request_id,seg_id:id,crossing_groups_json:JSON.stringify(groups.map(function(g,i){return g.segment_ids.indexOf(id)>=0?i:-1;}).filter(function(i){return i>=0;})),registry_version:r.registry_version,schema_version:PROPOSAL_SCHEMA};});
}
function membershipsComplete(r) {
  var actual=membershipRows(r),expected=expectedMemberships(r),seen={};
  if(actual.length!==expected.length||!expected.length)return false;
  return actual.every(function(x){if(seen[x.seg_id])return false;seen[x.seg_id]=true;return expected.some(function(e){return x.seg_id===e.seg_id&&x.crossing_groups_json===e.crossing_groups_json&&x.registry_version===e.registry_version&&x.schema_version===e.schema_version;});});
}
function finishMemberships(r) {
  requireHeaders('proposal_segments',MEMBERSHIP_HEADERS);
  var actual=membershipRows(r),expected=expectedMemberships(r),seen={};
  actual.forEach(function(x){if(seen[x.seg_id]||!expected.some(function(e){return e.seg_id===x.seg_id&&e.crossing_groups_json===x.crossing_groups_json&&e.registry_version===x.registry_version&&e.schema_version===x.schema_version;}))throw Error('membership_conflict');seen[x.seg_id]=true;});
  expected.forEach(function(e){if(!seen[e.seg_id]){sheet('proposal_segments').appendRow(sheetValues(MEMBERSHIP_HEADERS.map(function(k){return e[k];})));seen[e.seg_id]=true;}});
  if(!membershipsComplete(r))throw Error('membership_incomplete');
  updateParent(r,{ingestion_status:'complete'});
}
function saveProposalRecord(d) {
  if(d.registry_version!==ROAD_REGISTRY_VERSION)return {ok:false,error:'registry_version'};
  if(!validRequestId(d.request_id))return {ok:false,error:'request_id'};
  if(TYPES.indexOf(d.type)<0||REASONS.indexOf(d.reason)<0)return {ok:false,error:'choice'};
  if(!RoadGeometry.validPoint(d.a)||!RoadGeometry.validPoint(d.b))return {ok:false,error:'location'};
  if(d.story!==undefined&&(typeof d.story!=='string'||d.story.length>300))return {ok:false,error:'story'};
  var multi=d.segment_ids!==undefined;
  if(multi&&(!Array.isArray(d.segment_ids)||d.schema_version!==MULTI_PROTOCOL||d.validation_version!==ROAD_VALIDATION_VERSION))return {ok:false,error:'schema'};
  var a=d.a.map(round6),b=d.b.map(round6),match=matchAll(a,b);
  if(!match.ok)return {ok:false,error:match.reason};
  if(multi){
    if(!sameIds(d.segment_ids,match.segment_ids)||new Set(d.segment_ids).size!==d.segment_ids.length)return {ok:false,error:'segment_mismatch'};
    if(!Array.isArray(d.crossings)||d.crossings.length!==match.crossings.length||d.crossings.some(function(g,i){return !g||!sameIds(g.segment_ids,match.crossings[i].segment_ids)||!Number.isFinite(g.position_m)||Math.abs(g.position_m-match.crossings[i].position_m)>.02;}))return {ok:false,error:'crossing_mismatch'};
    if(match.status==='needs_review'&&(d.validation_status!=='needs_review'||d.review_requested!==true))return {ok:false,error:'review_required'};
    if(d.validation_status!=='valid'&&d.validation_status!=='needs_review')return {ok:false,error:'validation_status'};
  }else{
    var n=neighborhood(a,b),single=RoadGeometry.choose(a,b,n.features,n.guards);
    if(!single.ok||single.feature.properties.seg_id!==d.seg_id)return {ok:false,error:single.reason||'segment_mismatch'};
  }
  var status=multi&&d.validation_status==='needs_review'?'needs_review':match.status;
  var story=String(d.story||'').trim();
  var hash=parentHash(a,b,match.segment_ids,match.crossings,d.type,d.reason,story,status,ROAD_VALIDATION_VERSION),request=requestKey(d.request_id);
  var old=rows('proposals',PROPOSAL_HEADERS).filter(function(r){return requestKey(r.request_id)===request;});
  if(old.length){
    if(old.length!==1||old[0].payload_hash!==hash)return {ok:false,error:'request_id_conflict'};
    if(!storedParentIntact(old[0],false))return {ok:false,error:'stored_parent_conflict'};
    finishMemberships(old[0]);return {ok:true,received:true,status:'pending',request_id:request,segment_ids:match.segment_ids,replayed:true};
  }
  requireHeaders('proposals',PROPOSAL_HEADERS);
  var scalar=match.segment_ids.length===1?match.segment_ids[0]:(!multi?d.seg_id:'');
  var canonical=Number.isSafeInteger(scalar)?road(scalar):null;
  var reasons=match.review_reasons.slice();if(status!==match.status)reasons.push({code:'client_requested_review',segment_ids:match.segment_ids});
  var row={received:new Date(),seg_id:scalar,dist_m:canonical&&canonical.d!==null?canonical.d:'',a_lng:a[0],a_lat:a[1],b_lng:b[0],b_lat:b[1],type:d.type,reason:d.reason,
    story:story,story_status:story?'pending':'',status:'pending',schema_version:PROPOSAL_SCHEMA,registry_version:ROAD_REGISTRY_VERSION,request_id:request,review_status:'pending',
    validation_version:ROAD_VALIDATION_VERSION,validation_status:status,validation_review_status:'pending',validation_review_note:'',validation_review_hash:'',segment_ids_json:JSON.stringify(match.segment_ids),crossings_json:JSON.stringify(match.crossings),ingestion_status:'preparing',payload_hash:hash,review_reasons_json:JSON.stringify(reasons)};
  sheet('proposals').appendRow(sheetValues(PROPOSAL_HEADERS.map(function(k){return row[k];})));
  row._row=sheet('proposals').getLastRow();finishMemberships(row);
  return {ok:true,received:true,status:'pending',request_id:request,segment_ids:match.segment_ids,replayed:false};
}
function hardReviewReasons(r) {
  var forbidden=['bridge','tunnel','non_reference_level','controlled_access_carriageway','pedestrian_restriction','access_requires_review','nearby_grade_or_access_guard','crossing_angle','endpoint_clearance','tangent_vertex','collinear_overlap','validation_unavailable'];
  return parseArray(r.review_reasons_json).some(function(reason){return forbidden.indexOf(reason.code)>=0;});
}
// Trusted Script-editor/admin operation only. Deliberately absent from doPost.
// Tests invoke this against in-memory Sheets with explicitly synthetic evidence.
function reviewProposalRecord(request,decision,evidence) {
  var lock=LockService.getScriptLock();lock.waitLock(10000);roadRuntime={};
  try{
    var found=rows('proposals',PROPOSAL_HEADERS).filter(function(r){return requestKey(r.request_id)===requestKey(request);});
    if(found.length!==1)return {ok:false,error:'request_id'};
    var r=found[0];if(r.schema_version===PROPOSAL_SCHEMA&&(r.ingestion_status!=='complete'||!membershipsComplete(r)))return {ok:false,error:'ingestion_incomplete'};
    if(decision==='reject'){updateParent(r,{status:'rejected',review_status:'rejected',validation_review_status:'rejected'});return {ok:true};}
    if(decision!=='approve')return {ok:false,error:'decision'};
    if(r.schema_version===PROPOSAL_SCHEMA&&(r.registry_version!==ROAD_REGISTRY_VERSION||r.validation_version!==ROAD_VALIDATION_VERSION||!storedParentIntact(r,true)))return {ok:false,error:'validation_or_geometry_changed'};
    if(r.schema_version===PROPOSAL_SCHEMA&&hardReviewReasons(r))return {ok:false,error:'restricted_or_grade'};
    var patch={status:'ok',review_status:'approved'};
    if(r.schema_version===PROPOSAL_SCHEMA&&r.validation_status!=='valid'){
      if(!evidence||evidence.confirmed!==true||typeof evidence.note!=='string'||!evidence.note.trim())return {ok:false,error:'validation_review_required'};
      patch.validation_review_status='verified';patch.validation_review_note=evidence.note.slice(0,1000);patch.validation_review_hash=r.payload_hash;
    }
    updateParent(r,patch);return {ok:true};
  }finally{lock.releaseLock();}
}
function approvedParents() {
  var list=rows('proposals',PROPOSAL_HEADERS),counts={};
  list.forEach(function(r){var key=parentIdentity(r);counts[key]=(counts[key]||0)+1;});
  var seen={};return list.filter(function(r){
    if(r.status!=='ok'||r.review_status!=='approved'||TYPES.indexOf(r.type)<0||REASONS.indexOf(r.reason)<0)return false;
    var key=parentIdentity(r);if(seen[key])return false;
    if(r.schema_version===PROPOSAL_SCHEMA){
      if(counts[key]!==1||r.ingestion_status!=='complete'||r.registry_version!==ROAD_REGISTRY_VERSION||r.validation_version!==ROAD_VALIDATION_VERSION||!membershipsComplete(r)||!storedParentIntact(r,true)||hardReviewReasons(r))return false;
      if(r.validation_status!=='valid'&&!(r.validation_review_status==='verified'&&r.validation_review_note&&r.validation_review_hash===r.payload_hash))return false;
      r._ids=parseArray(r.segment_ids_json);if(!r._ids.length||r._ids.some(function(id){return !road(id);}))return false;
    }else{
      if(!Number.isSafeInteger(r.seg_id)||!road(r.seg_id)||r.validation_status==='needs_review')return false;
      r._ids=[r.seg_id];
    }
    seen[key]=true;r._identity=key;return true;
  });
}
function singleAggregateLine(list,canonical) {
  var usable=list.filter(function(r){return r._ids.length===1&&(r.schema_version===API_VERSION||r.schema_version===PROPOSAL_SCHEMA)&&RoadGeometry.validPoint([r.a_lng,r.a_lat])&&RoadGeometry.validPoint([r.b_lng,r.b_lat]);});
  if(usable.length<LINE_MIN)return null;
  var pairs=usable.map(function(r){var a=[r.a_lng,r.a_lat],b=[r.b_lng,r.b_lat];return a[0]>b[0]||(a[0]===b[0]&&a[1]>b[1])?[b,a]:[a,b];});
  function mean(i,j){return round4(pairs.reduce(function(n,p){return n+Number(p[i][j]);},0)/pairs.length);}
  var line=[[mean(0,0),mean(0,1)],[mean(1,0),mean(1,1)]],length=RoadGeometry.metres(line[0],line[1]);
  return length>=2&&length<=80&&RoadGeometry.hits(line[0],line[1],canonical.g).length?line:null;
}
function publicationState() {
  policy();var parents=approvedParents(),groups={},support={},supportSeen={};
  parents.forEach(function(r){r._ids.forEach(function(id){(groups[id]||(groups[id]=[])).push(r);});});
  rows('support',SUPPORT_HEADERS).forEach(function(r){var k=r.request_id?'request:'+requestKey(r.request_id):'legacy:'+r._row;if(r.status==='ok'&&!supportSeen[k]){supportSeen[k]=true;support[r.seg_id]=(support[r.seg_id]||0)+1;}});
  var ids=Object.keys(groups).map(Number).filter(function(id){return groups[id].length>=MIN_PROPOSALS;}).sort(function(a,b){return a-b;}),published={},visible={};
  ids.forEach(function(id){published[id]=true;groups[id].forEach(function(r){visible[r._identity]=r;});});
  var segments=ids.map(function(id){var list=groups[id],canonical=road(id),types={},reasons={};list.forEach(function(r){types[r.type]=(types[r.type]||0)+1;reasons[r.reason]=(reasons[r.reason]||0)+1;});var tt=top(types),tr=top(reasons),c=canonical.g.type==='LineString'?canonical.g.coordinates:canonical.g.coordinates[0],center=c[Math.floor(c.length/2)],latest=list.reduce(function(n,r){var t=new Date(r.received).getTime();return isFinite(t)?Math.max(n,t):n;},0);
    return {seg_id:id,road:'Road segment '+id,count:list.length,support:support[id]||0,dist_m:canonical.d,top_type:tt.key+' ('+tt.n+' of '+list.length+')',top_reason:tr.key+' ('+tr.n+' of '+list.length+')',line:singleAggregateLine(list,canonical),center:[round3(center[0]),round3(center[1])],reviewed:true,last_updated:latest?Utilities.formatDate(new Date(latest),'Asia/Singapore','d MMM yyyy'):'-'};});
  var cohorts={};parents.filter(function(r){return r._ids.length>1&&r._ids.every(function(id){return published[id];});}).forEach(function(r){
    var topology=parseArray(r.crossings_json).map(function(g){return sortedIds(g.segment_ids);});
    if(r.a_lng>r.b_lng||(r.a_lng===r.b_lng&&r.a_lat>r.b_lat))topology.reverse();
    var key=JSON.stringify([sortedIds(r._ids),topology]);(cohorts[key]||(cohorts[key]=[])).push(r);
  });
  var crossings=[];Object.keys(cohorts).forEach(function(k){var list=cohorts[k];if(list.length<LINE_MIN)return;
    var pairs=list.map(function(r){var a=[r.a_lng,r.a_lat],b=[r.b_lng,r.b_lat];return a[0]>b[0]||(a[0]===b[0]&&a[1]>b[1])?[b,a]:[a,b];});
    function mean(i,j){return Math.round(pairs.reduce(function(n,p){return n+Number(p[i][j]);},0)/pairs.length*1e5)/1e5;}
    var line=[[mean(0,0),mean(0,1)],[mean(1,0),mean(1,1)]],length=RoadGeometry.metres(line[0],line[1]);
    if(length<2||length>80)return;
    var nearby=neighborhood(line[0],line[1]),raw=RoadGeometry.contacts(line[0],line[1],nearby.features),hitIds=[];raw.contacts.forEach(function(h){var id=h.feature.properties.seg_id;if(hitIds.indexOf(id)<0)hitIds.push(id);});
    if(raw.overlaps.length||!sameIds(sortedIds(hitIds),sortedIds(list[0]._ids)))return;
    var displayMatch=RoadGeometry.select(line[0],line[1],nearby.features,crossingEvidence(line[0],line[1],nearby.features));
    if(!displayMatch.ok||hardReviewReasons({review_reasons_json:JSON.stringify(displayMatch.review_reasons)}))return;
    if(JSON.stringify(displayMatch.crossings.map(function(g){return sortedIds(g.segment_ids);}))!==JSON.stringify(JSON.parse(k)[1]))return;
    // At most one feature per approved parent, never one per road membership.
    // Coordinates are a >=3-parent cohort aggregate, not individual input points.
    list.forEach(function(r){crossings.push({id:'proposal-'+digest(r._identity+'|'+ROAD_REGISTRY_VERSION).slice(0,24),segment_ids:displayMatch.segment_ids.slice(),geometry:{type:'LineString',coordinates:line},reviewed:true,validation_status:'validated',coordinate_basis:'approved_cohort_aggregate',cohort_count:list.length});});
  });
  var visibleParents=Object.keys(visible).map(function(k){return visible[k];}),latest=visibleParents.reduce(function(n,r){var t=new Date(r.received).getTime();return isFinite(t)?Math.max(n,t):n;},0);
  return {segments:segments,crossings:crossings,summary:{ok:true,scope:'published_only',proposals:visibleParents.length,segments:segments.length,road_memberships:segments.reduce(function(n,s){return n+s.count;},0),crossings:crossings.length,lastUpdated:latest?Utilities.formatDate(new Date(latest),'Asia/Singapore','d MMM yyyy'):'-'}};
}
