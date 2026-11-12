// Earnly V5.1 protected paid resource endpoint.
// Deploy as a NEW function with JWT verification OFF; Telegram initData is verified here.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
const allowedOrigin='https://earnly-global.github.io';
const cors={'Access-Control-Allow-Origin':allowedOrigin,'Access-Control-Allow-Headers':'content-type','Access-Control-Allow-Methods':'POST, OPTIONS','Vary':'Origin'};
const json=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{...cors,'Content-Type':'application/json','Cache-Control':'no-store'}});
const enc=new TextEncoder();
function hex(bytes:Uint8Array){return Array.from(bytes).map(x=>x.toString(16).padStart(2,'0')).join('');}
async function hmac(key:CryptoKey,data:string){return new Uint8Array(await crypto.subtle.sign('HMAC',key,enc.encode(data)));}
async function keyFor(bytes:Uint8Array){return crypto.subtle.importKey('raw',bytes,{name:'HMAC',hash:'SHA-256'},false,['sign']);}
async function verifyInitData(raw:string,token:string){
  if(!raw||raw.length>8192)return null;
  const params=new URLSearchParams(raw), supplied=params.get('hash');
  if(!supplied||!/^[0-9a-f]{64}$/i.test(supplied))return null;
  const authDate=Number(params.get('auth_date'));
  if(!Number.isSafeInteger(authDate)||Math.abs(Date.now()/1000-authDate)>3600)return null;
  const check=Array.from(params.entries()).filter(([k])=>k!=='hash').sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>`${k}=${v}`).join('\n');
  const secret=await hmac(await keyFor(enc.encode('WebAppData')),token);
  const digest=hex(await hmac(await keyFor(secret),check));
  // Constant-time compare of fixed-length digest strings.
  let diff=0;for(let i=0;i<64;i++)diff|=digest.charCodeAt(i)^supplied.toLowerCase().charCodeAt(i);
  if(diff!==0)return null;
  try{const user=JSON.parse(params.get('user')||'null');return Number.isSafeInteger(user?.id)&&user.id>0?user.id:null;}catch{return null;}
}
// V5: protected catalog endpoint. Never trust client-provided tier or Telegram user ID.
Deno.serve(async req=>{
 if(req.method==='OPTIONS')return new Response(null,{status:204,headers:cors});
 if(req.method!=='POST')return json({error:'Method not allowed'},405);
 const origin=req.headers.get('origin');if(origin&&origin!==allowedOrigin)return json({error:'Origin not allowed'},403);
 let input:any;try{input=await req.json()}catch{return json({error:'Invalid JSON'},400)}
 const token=Deno.env.get('TELEGRAM_BOT_TOKEN'),url=Deno.env.get('SUPABASE_URL'),service=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
 if(!token||!url||!service)return json({error:'Server configuration missing'},503);
 const telegramId=await verifyInitData(String(input.initData||''),token);
 if(!telegramId)return json({error:'Telegram authentication failed or expired'},401);
 const db=createClient(url,service,{auth:{persistSession:false,autoRefreshToken:false}});
 const {data:user,error:ue}=await db.from('earnly_users').select('id').eq('telegram_id',telegramId).maybeSingle();
 if(ue)return json({error:'Account lookup failed'},503);
 if(!user)return json({error:'Account not initialized'},404);
 const {data:m,error:me}=await db.from('memberships').select('tier,status,expires_at').eq('user_id',user.id).maybeSingle();
 if(me)return json({error:'Membership lookup failed'},503);
 const tier=m?.status==='active'&&(m.expires_at===null||m.expires_at===undefined||Date.parse(m.expires_at)>Date.now())&&['premium','vip'].includes(m.tier)?m.tier:'free';
 const action=String(input.action||'premium_resources');
 const required=action==='vip_resources'?'vip':action==='premium_resources'?'premium':null;
 if(!required)return json({error:'Unknown action'},400);
 if(tier==='free'||(required==='vip'&&tier!=='vip'))return json({error:'Active '+required+' membership required',code:'MEMBERSHIP_REQUIRED'},403);
 const {data,error}=await db.from('earnly_paid_resources').select('id,title,description,url,category,minimum_tier,created_at').eq('published',true).eq('minimum_tier',required).order('created_at',{ascending:false}).limit(50);
 if(error)return json({error:'Protected resources unavailable'},503);
 const resources=data||[];
 return json({ok:true,tier,resources,notice:'Provider availability, eligibility and payouts require independent verification.'});
});
