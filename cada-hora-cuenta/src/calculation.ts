import { supabase } from './client';
import type { PlanDocument } from './types';
export type Calculation = {
  status:string;run_id:string;version:number;revision_id:string|null;revision_status:string;source:string;
  document?:PlanDocument;last_observed_month?:number;projected_months?:number[];
  validation?:{matched:number;reference_cases:number;different:number;missing:number};
  changes?:{professional_id:string;institute_id:number;month:number;kind:string;effective_from:string;meta_before:number;meta_after:number;meta_delta:number;before:any;after:any}[];
  warnings?:{code:string;message:string;professional_id?:string;institute_id?:number;month?:number;sheet?:string;row?:number}[];
};
const configured=import.meta.env.VITE_CALC_API_URL?.replace(/\/$/,'');
export const calculationEnabled=!!configured||import.meta.env.DEV;
async function call<T>(path:string,body?:unknown,method='GET'):Promise<T>{
  if(!calculationEnabled)throw new Error('La API de cálculo no está configurada. Define VITE_CALC_API_URL en el despliegue.');
  const headers:Record<string,string>={};
  if(supabase){const{data}=await supabase.auth.getSession();if(data.session)headers.Authorization=`Bearer ${data.session.access_token}`;}
  if(body!==undefined)headers['Content-Type']='application/json';
  const response=await fetch((configured||'/calc-api')+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(60000)});
  let data:any;
  try{data=await response.json();}catch{throw new Error('La API de cálculo no responde. Inicia python -m server.app en la VM o configura su URL HTTPS.');}
  if(!response.ok)throw new Error(data.errors?.map((e:any)=>`${e.sheet||''}${e.row?' / fila '+e.row:''}: ${e.message}`).join('\n')||data.error||'Fallo del cálculo');
  return data;
}
export const latestCalculation=()=>call<Calculation|null>('/api/latest');
export const getParameters=()=>call<{params:any;hash:string;history:any[]}>('/api/parameters');
export const saveParameters=(params:unknown)=>call('/api/parameters',{params},'PUT');
export const recalculate=()=>call<Calculation>('/api/recalculate',{},'POST');
export async function sendKit(file:File){
  if(!file.name.toLowerCase().endsWith('.xlsx')||file.size>20*1024*1024)throw new Error('Selecciona el Excel plano de hasta 20 MB generado por bot_traductor.py.');
  const bytes=new Uint8Array(await file.arrayBuffer());let binary='';
  for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  return call<Calculation>('/api/batches',{kit_base64:btoa(binary),filename:file.name},'POST');
}
