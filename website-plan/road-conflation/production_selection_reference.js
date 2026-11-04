// Offline integration reference only. The live website is not modified.
// Inputs are projected screen coordinates; caller enforces zoom and 80 m limit.
function pointSegmentDistance(p, a, b) {
  const dx=b[0]-a[0], dy=b[1]-a[1], d=dx*dx+dy*dy;
  const t=d ? Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/d)) : 0;
  return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);
}
function crosses(a,b,c,d) {
  const rx=b[0]-a[0], ry=b[1]-a[1], sx=d[0]-c[0], sy=d[1]-c[1];
  const denom=rx*sy-ry*sx;
  if(Math.abs(denom)<1e-10) return false; // Collinear A/B is not across a road.
  const qx=c[0]-a[0], qy=c[1]-a[1];
  const t=(qx*sy-qy*sx)/denom, u=(qx*ry-qy*rx)/denom;
  return t>1e-8 && t<1-1e-8 && u>=-1e-8 && u<=1+1e-8;
}
function chooseCrossedRoad(features,a,b) {
  const mid=[(a[0]+b[0])/2,(a[1]+b[1])/2], seen=new Set();
  let best=null, distance=Infinity;
  for(const feature of features) {
    const id=String(feature.seg_id);
    if(seen.has(id)) continue;
    seen.add(id);
    let crossed=false, nearest=Infinity;
    for(let i=1;i<feature.screen.length;i++) {
      const c=feature.screen[i-1],d=feature.screen[i];
      crossed=crossed||crosses(a,b,c,d);
      nearest=Math.min(nearest,pointSegmentDistance(mid,c,d));
    }
    if(crossed && (nearest<distance-1e-8 || (Math.abs(nearest-distance)<=1e-8 && best && feature.seg_id<best.seg_id))) {
      best=feature;distance=nearest;
    }
  }
  return best;
}
module.exports={chooseCrossedRoad,pointSegmentDistance,crosses};
