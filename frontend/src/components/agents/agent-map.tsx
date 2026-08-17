"use client";

import { useEffect, useRef } from "react";
import { APIProvider, Map, Marker, useMap } from "@vis.gl/react-google-maps";

type Agent = { id:number; employee_name:string; shift_status:string; last_latitude:string|null; last_longitude:string|null };
type Point = { latitude:string; longitude:string; received_at:string };
type RouteData = { points:Point[] };

export function AgentMap({agents,selectedAgentId,routes,onSelect}:{agents:Agent[];selectedAgentId:number|null;routes:Record<number,RouteData>;onSelect:(id:number)=>void}){
  const apiKey=process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  const located=agents.filter(agent=>agent.last_latitude&&agent.last_longitude);
  if(!apiKey)return <div className="flex h-[460px] items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 p-8 text-center"><div><p className="text-sm font-bold text-slate-900">Google Maps API key required</p><p className="mt-2 max-w-md text-xs leading-5 text-slate-600">Set <code className="rounded bg-slate-200 px-1.5 py-1">NEXT_PUBLIC_GOOGLE_MAPS_API_KEY</code> in <code className="rounded bg-slate-200 px-1.5 py-1">frontend/.env.local</code>, then restart Next.js.</p></div></div>;
  const center=selectedAgentId&&routes[selectedAgentId]?.points.at(-1)?toLatLng(routes[selectedAgentId].points.at(-1)!):located[0]?{lat:Number(located[0].last_latitude),lng:Number(located[0].last_longitude)}:{lat:8.1833,lng:77.4119};
  return <APIProvider apiKey={apiKey}><Map defaultCenter={center} defaultZoom={14} mapId="zchit-agent-monitor" gestureHandling="greedy" disableDefaultUI={false} className="h-[460px] w-full rounded-lg"><RouteLines routes={routes} selectedAgentId={selectedAgentId}/>{located.map(agent=><Marker key={agent.id} position={{lat:Number(agent.last_latitude),lng:Number(agent.last_longitude)}} title={agent.employee_name} onClick={()=>onSelect(agent.id)} label={{text:agent.employee_name.slice(0,1).toUpperCase(),color:"white",fontWeight:"700"}}/>)}</Map></APIProvider>;
}
function RouteLines({routes,selectedAgentId}:{routes:Record<number,RouteData>;selectedAgentId:number|null}){const map=useMap();const lines=useRef<google.maps.Polyline[]>([]);useEffect(()=>{if(!map||!window.google)return;lines.current.forEach(line=>line.setMap(null));lines.current=Object.entries(routes).map(([agentId,data])=>new google.maps.Polyline({map,path:data.points.map(toLatLng),strokeColor:Number(agentId)===selectedAgentId?"#059669":"#64748b",strokeOpacity:Number(agentId)===selectedAgentId?1:.55,strokeWeight:Number(agentId)===selectedAgentId?5:3,geodesic:true}));return()=>{lines.current.forEach(line=>line.setMap(null));lines.current=[];};},[map,routes,selectedAgentId]);return null;}
function toLatLng(point:Point){return{lat:Number(point.latitude),lng:Number(point.longitude)};}
