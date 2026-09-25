import { test, expect } from '@playwright/test';
import { readFile, readdir, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

/** Serve source modules only inside the intercepted browser test origin. */
async function harness(page) {
  await page.route("**/assets/vehicles/**", async route => route.fulfill({contentType:"image/svg+xml",body:await readFile(resolve(new URL(route.request().url()).pathname.slice(1)),"utf8")}));
  await page.route('**/__modules__/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/__modules__/', '');
    if (path === 'maplibre.js') return route.fulfill({contentType:'text/javascript',body:'export const Marker=window.maplibregl.Marker;export const Popup=window.maplibregl.Popup;export const LngLatBounds=window.maplibregl.LngLatBounds;'});
    const source = await readFile(resolve(path), 'utf8');
    await route.fulfill({contentType:'text/javascript',body:source.replaceAll('from "maplibre-gl"','from "/__modules__/maplibre.js"')});
  });
  await page.route('**/__harness__', route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html><head></head><body><div id="map" style="width:100vw;height:100vh"></div></body></html>'}));
  await page.goto('/__harness__');
  await page.addStyleTag({path:'frontend/style.css'});
  await page.addStyleTag({path:'node_modules/maplibre-gl/dist/maplibre-gl.css'});
  await page.evaluate(async()=>{window.maplibregl=await import('/__modules__/node_modules/maplibre-gl/dist/maplibre-gl.mjs');window.maplibregl.setWorkerUrl('/__modules__/node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs');});
  await mkdir('artifacts/map-regressions',{recursive:true});
}

test('all model roles preserve alpha and protected parts while coloring explicit body masks',async({page})=>{
 test.setTimeout(120000);
 await harness(page);
 const models=await readdir('assets/vehicles');
 const results=await page.evaluate(async(models)=>{
  const {composeVehiclePaint,originalVehicleSvg}=await import('/__modules__/frontend/vehicle-paint.js');
  async function pixels(svg,width,height){const img=new Image();img.src=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));await img.decode();const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0,width,height);URL.revokeObjectURL(img.src);return ctx.getImageData(0,0,width,height).data;}
  const results=[];
  for(const model of models)for(const role of ['front','side-left','map']){
   const path=`/assets/vehicles/${model}/${role}`;
   const [source,mask]=await Promise.all([fetch(path+'.svg').then(r=>r.text()),fetch(path+'-paint.svg').then(r=>r.text())]);
   const base=originalVehicleSvg(source);const painted=await composeVehiclePaint(source,mask,'#4c78a8');
   const [a,b,m]=await Promise.all([pixels(base.svg,base.width,base.height),pixels(painted,base.width,base.height),pixels(mask,base.width,base.height)]);
   let alphaChanges=0,protectedChanges=0,paintChanges=0;
   for(let i=0;i<a.length;i+=4){if(a[i+3]!==b[i+3])alphaChanges++;const changed=Math.abs(a[i]-b[i])+Math.abs(a[i+1]-b[i+1])+Math.abs(a[i+2]-b[i+2]);if(a[i+3]===255 && m[i]*m[i+3]===0 && changed)protectedChanges++;if(changed>20 && m[i]>0)paintChanges++;}
   const proofWidth=role==='front'?200:role==='side-left'?350:base.width/base.height*200;
   const left=role==='front'?165:role==='side-left'?440:950-proofWidth/2;
   const sample=(x,y)=>{const i=(Math.floor((y-5)/200*base.height)*base.width+Math.floor((x-left)/proofWidth*base.width))*4;return [...a.slice(i,i+4)].every((v,k)=>v===b[i+k]);};
   const van=['iveco_daily_35s18','mercedes_sprinter_317_cdi','vw_crafter_35_130kw'].includes(model);
   const protectedPart=role==='front'?sample(265,80)&&sample(265,van?136:144)&&sample(212,185):role==='map'?sample(950,('man_tgl_12_250 mercedes_atego_1224_l mercedes_atego_818_l'.includes(model)?17:43)):sample(model==='mercedes_eactros_600'?478:van?551:('man_tgl_12_250 mercedes_atego_1224_l mercedes_atego_818_l'.includes(model)?490:525),model==='mercedes_eactros_600'?116:van?94:88);
   results.push({model,role,alphaChanges,protectedChanges,paintChanges,protectedPart});
  }
  return results;
 },models);
 for(const result of results){expect(result.alphaChanges,JSON.stringify(result)).toBe(0);expect(result.protectedChanges,JSON.stringify(result)).toBe(0);expect(result.paintChanges,JSON.stringify(result)).toBeGreaterThan(100);expect(result.protectedPart,JSON.stringify(result)).toBe(true);}
});

async function setupMap(page) {
 await harness(page);
 await page.evaluate(async()=>{
  const {addOverlayLayers}=await import('/__modules__/frontend/map/layers.js');
  const {VehicleGroups}=await import('/__modules__/frontend/map/vehicle-groups.js');
  const {VehicleColorAssets}=await import('/__modules__/frontend/vehicle-color-assets.js');
  const {VehicleIconRegistry}=await import('/__modules__/frontend/map/vehicle-assets.js');
  const map=new window.maplibregl.Map({container:'map',style:{version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#70828c'}}]},center:[13,52],zoom:14,attributionControl:false,canvasContextAttributes:{preserveDrawingBuffer:true}});
  await new Promise(resolve=>map.on('load',resolve));addOverlayLayers(map);
  const assets=new VehicleColorAssets(path=>fetch(path).then(r=>r.text()));
  const registry=new VehicleIconRegistry(map,path=>fetch(path).then(r=>r.text()),{coloredSource:assets.source.bind(assets)});
  await registry.ensure([{model_id:'daf_xg_plus_480',player_color:'#4c78a8'},{model_id:'daf_xg_plus_480',player_color:'#4c78a8',role:'front'}]);
  const groups=new VehicleGroups(map,()=>{},()=>false);
  const feature=(id,idle=false)=>({type:'Feature',geometry:{type:'Point',coordinates:[13,52]},properties:{key:'own:'+id,id,vehicleId:id,isOwn:true,idle,movementState:idle?'idle':'enroute',modelId:'daf_xg_plus_480',modelName:'DAF XG+',bearing:0,playerColor:'#4c78a8',hasIcon:true,iconImage:'vehicle-daf_xg_plus_480-4c78a8'+(idle?'-front':'')}});
  window.proof={map,groups,feature,assets,registry};
  window.drawProof=async(features,selected='')=>{
   const shown=groups.update(features,selected,true);for (const [name, own] of [['vehicles',true],['multiplayer-vehicles',false]]) map.getSource(name).setData({type:'FeatureCollection',features:shown.filter(f=>f.properties.isOwn===own)});await new Promise(resolve=>{map.once('idle',resolve);map.triggerRepaint();});return shown.map(f=>f.properties.key);
  };
 });
}

test('real singleton and grouped sprites render compass bearings, status separation and transparent badges',async({page})=>{
 await setupMap(page);
 test.setTimeout(60000);
 for(const rotation of [0,45])for(const grouped of [false,true])for(const bearing of [0,90,180,270,45]){
  await page.evaluate(async({grouped,bearing,rotation})=>{const {feature,map}=window.proof;map.jumpTo({bearing:rotation});const a=feature('a');a.properties.bearing=bearing;const b=feature('b');b.properties.bearing=bearing+40;await window.drawProof(grouped?[a,b]:[a]);},{grouped,bearing,rotation});
  expect(await page.locator('.vehicle-group').count()).toBe(grouped?1:0);
  if(grouped){await expect(page.locator('.vehicle-group')).toHaveText('2');expect(await page.locator('.vehicle-group').evaluate(e=>getComputedStyle(e).backgroundColor)).toBe('rgba(0, 0, 0, 0)');}
  const bounds=await page.evaluate(()=>{const {map}=window.proof;const gl=map.getCanvas().getContext('webgl2');const w=gl.drawingBufferWidth,h=gl.drawingBufferHeight;const pixels=new Uint8Array(w*h*4);gl.readPixels(0,0,w,h,gl.RGBA,gl.UNSIGNED_BYTE,pixels);const xs=[],ys=[];let wx=0,wy=0,weight=0;for(let y=h/2-85;y<h/2+85;y++)for(let x=w/2-85;x<w/2+85;x++){const i=(y*w+x)*4;const white=Math.max(0,Math.min(pixels[i],pixels[i+1],pixels[i+2])-150);wx+=(x-w/2)*white;wy+=(y-h/2)*white;weight+=white;if(Math.abs(pixels[i]-112)+Math.abs(pixels[i+1]-130)+Math.abs(pixels[i+2]-140)>50){xs.push(x);ys.push(y);}}return {width:Math.max(...xs)-Math.min(...xs),height:Math.max(...ys)-Math.min(...ys),cabX:wx/weight,cabY:wy/weight};});
  expect(bounds.cabX*Math.sin((bearing-rotation)*Math.PI/180)+bounds.cabY*Math.cos((bearing-rotation)*Math.PI/180)).toBeGreaterThan(0);
  if((bearing-rotation)%180===0)expect(bounds.height).toBeGreaterThan(bounds.width*2);
  if(Math.abs(bearing-rotation)%180===90)expect(bounds.width).toBeGreaterThan(bounds.height*2);
  await page.screenshot({path:`artifacts/map-regressions/${grouped?'group':'single'}-${bearing}${rotation?'-rotated':''}.png`});
 }
 await page.evaluate(async()=>{const {feature,map}=window.proof;map.jumpTo({bearing:0});await window.drawProof([feature('idle-a',true),feature('idle-b',true),feature('moving-a'),feature('moving-b')]);});
 await expect(page.locator('.vehicle-group')).toHaveCount(2);
 expect(await page.locator('.vehicle-group').evaluateAll(nodes=>nodes.map(n=>n.dataset.movement).sort())).toEqual(['enroute','idle']);
 await page.screenshot({path:'artifacts/map-regressions/separate-statuses.png'});
 const selected=await page.evaluate(async()=>{const {feature}=window.proof;return window.drawProof([feature('a'),feature('b')],'a');});
 expect(selected).toEqual(['own:a','own:b']);await expect(page.locator('.vehicle-group')).toHaveCount(0);
 await page.evaluate(async()=>{const {feature,map}=window.proof;map.jumpTo({bearing:45});await window.drawProof([feature('a',true),feature('b',true)]);});
 await page.screenshot({path:'artifacts/map-regressions/idle-rotated-map.png'});
 await page.evaluate(async()=>{const {feature,map}=window.proof;map.jumpTo({bearing:0});const items=['a','b'].map(id=>{const f=feature(id);Object.assign(f.properties,{isOwn:false,ownerId:'other',key:'other:'+id,username:'Other company'});return f;});await window.drawProof(items);});
 await expect(page.locator('.vehicle-group')).toHaveCount(1);
 await expect(page.locator('.vehicle-group')).toHaveAttribute('aria-label',/fremde/);
 await page.screenshot({path:'artifacts/map-regressions/foreign-group.png'});
});

test('real camera consumes delayed navigation, ignores polling and frames the current vehicle',async({page})=>{
 await setupMap(page);
 const result=await page.evaluate(async()=>{
  const {MapCamera}=await import('/__modules__/frontend/map/camera.js');
  const {MapFocusController}=await import('/__modules__/frontend/controllers/map-focus-controller.js');
  const map=window.proof.map;const state=new EventTarget();state.now=()=>50;
  const origin={lon:13,lat:52,city_uid:'a'},destination={lon:15,lat:53,city_uid:'b'};
  const trip={id:'t',vehicle_id:'v',origin,destination,start:{lon:12,lat:51},departed_at:0,arrives_at:100,journey:{distance_km:100,segments:[{phase:'driving',starts_at:0,ends_at:100,start_km:0,end_km:100}]},route_geojson:{type:'LineString',coordinates:[[12,51],[13,52],[15,53]]}};
  state.data={vehicles:[{id:'v',name:'DAF',status:'enroute',hub:origin}],transports:[trip],contracts:[{id:'c',origin,destination}]};
  const camera=new MapCamera(map,()=>true,()=>({width:1440,height:900,panelOpen:true}));
  const controller=new MapFocusController({state,view:{cities:[origin],cityUid:''},map:{ready:true,map,camera,focusRoute:route=>camera.fitRoute(route.coordinates)}});controller.start();
  controller.select(new URL('http://test/fleet/v'));const vehicleZoom=map.getZoom();
  map.jumpTo({center:[2,40],zoom:7});for(let i=0;i<5;i++)state.dispatchEvent(new Event('change'));const free=map.getCenter().toArray();
  controller.cancel();controller.select(new URL('http://test/transports/t'));const tripZoom=map.getZoom();
  controller.cancel();controller.select(new URL('http://test/fleet/v'));const backZoom=map.getZoom();
  controller.destroy();return {vehicleZoom,tripZoom,backZoom,free};
 });
 expect(result.vehicleZoom).toBeGreaterThan(result.tripZoom);expect(result.backZoom).toBeCloseTo(result.vehicleZoom);expect(result.free).toEqual([2,40]);
 await page.screenshot({path:'artifacts/map-regressions/vehicle-focus.png'});
});


test('rendered idle facility projection restores independently of order markers',async({page})=>{
 await setupMap(page);
 await page.evaluate(async()=>{
  const {OverlayData}=await import('/__modules__/frontend/map/overlay-data.js');
  const {map,feature}=window.proof;
  const hub={id:'h',facility_uid:'h',city_uid:'a',city:'Alpha',resolution_status:'resolved',lon:13,lat:52};
  const overlay=new OverlayData();overlay.update({vehicles:[{id:'a',status:'idle',hub,hub_id:'h'}],transports:[],contracts:[]});
  window.proof.overlay=overlay;
  map.getSource('orders').setData({type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'Point',coordinates:[13.003,52]},properties:{id:'order'}}]});
  map.getSource('hubs').setData(overlay.hubFeatures([feature('a',true)]));
  await window.drawProof([feature('a',true)]);
 });
 expect(await page.evaluate(()=>window.proof.map.queryRenderedFeatures({layers:['hub-points']}).length)).toBe(0);
 expect(await page.evaluate(()=>window.proof.map.queryRenderedFeatures({layers:['orders']}).length)).toBe(1);
 await page.screenshot({path:'artifacts/map-regressions/facility-suppressed.png'});
 await page.evaluate(async()=>{const {map,overlay}=window.proof;map.getSource('hubs').setData(overlay.hubFeatures([]));await window.drawProof([]);});
 expect(await page.evaluate(()=>window.proof.map.queryRenderedFeatures({layers:['hub-points']}).length)).toBe(1);
 expect(await page.evaluate(()=>window.proof.map.queryRenderedFeatures({layers:['orders']}).length)).toBe(1);
 await page.screenshot({path:'artifacts/map-regressions/facility-restored.png'});
});
