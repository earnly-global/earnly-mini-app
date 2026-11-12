import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { webcrypto } from 'node:crypto';

const NOW = Date.now();
const TOKEN = 'LOCAL_DUMMY_BOT_TOKEN_NEVER_PRODUCTION';
const source = readFileSync(new URL('../src/earnly-paid-access.snapshot.ts', import.meta.url), 'utf8');
const records = new Map();
const catalog = [
 {id:1,title:'Premium sample',minimum_tier:'premium',published:true,created_at:'2026-01-01'},
 {id:2,title:'VIP sample',minimum_tier:'vip',published:true,created_at:'2026-01-02'},
 {id:3,title:'Draft',minimum_tier:'premium',published:false,created_at:'2026-01-03'}
];
let dbCalls=0;
function dbMock(){return {from(table){
 dbCalls++;
 const state={table,filters:[],limit:Infinity};
 const chain={
  select(){return chain},eq(k,v){state.filters.push([k,v]);return chain},
  order(){return chain},limit(n){state.limit=n;return chain},
  async maybeSingle(){
   const tid=state.filters.find(([k])=>k==='telegram_id')?.[1];
   if(table==='earnly_users')return {data:records.has(tid)?{id:tid}:null,error:null};
   if(table==='memberships')return {data:records.get(state.filters.find(([k])=>k==='user_id')?.[1])??null,error:null};
   throw Error('Unexpected maybeSingle: '+table);
  },
  then(resolve,reject){
   if(table!=='earnly_paid_resources')return Promise.reject(Error('Unexpected list: '+table)).then(resolve,reject);
   const data=catalog.filter(r=>state.filters.every(([k,v])=>r[k]===v)).slice(0,state.limit);
   return Promise.resolve({data,error:null}).then(resolve,reject);
  }
 };return chain;
}};}
let handler;
const js = source
 .replace(/^import .*;\s*$/m,'')
 .replace(/:Uint8Array/g,'').replace(/:CryptoKey/g,'').replace(/:string/g,'')
 .replace(/:unknown/g,'').replace(/:any/g,'')
 .replace(/\(r:any\)/g,'(r)');
runInNewContext(js,{
 Deno:{env:{get:k=>({TELEGRAM_BOT_TOKEN:TOKEN,SUPABASE_URL:'https://local.invalid',SUPABASE_SERVICE_ROLE_KEY:'DUMMY'}[k])},serve:fn=>{handler=fn}},
 createClient:()=>dbMock(),crypto:webcrypto,TextEncoder,URLSearchParams,Response,Date,JSON,Number,String,Array,Promise,Uint8Array,console
},{filename:'earnly-paid-access.snapshot.ts'});
assert.equal(typeof handler,'function');
async function signedInitData(id, seconds=Math.floor(Date.now()/1000)){
 const fields=new URLSearchParams({auth_date:String(seconds),user:JSON.stringify({id,first_name:'Local'})});
 const check=Array.from(fields.entries()).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>`${k}=${v}`).join('\n');
 const enc=new TextEncoder();
 const importKey=b=>webcrypto.subtle.importKey('raw',b,{name:'HMAC',hash:'SHA-256'},false,['sign']);
 const sign=(k,data)=>webcrypto.subtle.sign('HMAC',k,enc.encode(data));
 const secret=await sign(await importKey(enc.encode('WebAppData')),TOKEN);
 const digest=new Uint8Array(await sign(await importKey(secret),check));
 fields.set('hash',Buffer.from(digest).toString('hex'));
 return fields.toString();
}
async function request(id,action,raw){
 const response=await handler(new Request('https://local.invalid/',{method:'POST',headers:{origin:'https://earnly-global.github.io','content-type':'application/json'},body:JSON.stringify({action,initData:raw??await signedInitData(id)})}));
 return {status:response.status,body:await response.json()};
}
function fixture(id,tier,status='active',expires_at=new Date(NOW+86400000).toISOString()){
 records.set(id,{tier,status,expires_at});
}

test('rejects missing/invalid Telegram signature before database access',async()=>{
 dbCalls=0;const r=await request(101,'premium_resources','invalid-test-data');
 assert.equal(r.status,401);assert.equal(dbCalls,0);
});
test('rejects expired signed Telegram initData',async()=>{
 const r=await request(101,'premium_resources',await signedInitData(101,Math.floor(Date.now()/1000)-7200));assert.equal(r.status,401);
});
test('rejects tampered signed user ID',async()=>{
 const raw=await signedInitData(101);const tampered=raw.replace('101','102');
 assert.equal((await request(101,'premium_resources',tampered)).status,401);
});
test('Free: both paid resource endpoints deny access',async()=>{
 fixture(101,'free');for(const action of ['premium_resources','vip_resources'])assert.equal((await request(101,action)).status,403);
});
test('Premium: Premium 200, VIP 403; no VIP-only resources leak',async()=>{
 fixture(102,'premium');const p=await request(102,'premium_resources');
 assert.equal(p.status,200);assert.deepEqual(Array.from(p.body.resources,r=>r.minimum_tier),['premium']);
 assert.equal((await request(102,'vip_resources')).status,403);
});
test('VIP: Premium and VIP endpoints return separate tier catalogs',async()=>{
 fixture(103,'vip');const p=await request(103,'premium_resources');const v=await request(103,'vip_resources');
 assert.equal(p.status,200);assert.equal(v.status,200);
 assert.deepEqual(Array.from(p.body.resources,r=>r.minimum_tier),['premium']);
 assert.deepEqual(Array.from(v.body.resources,r=>r.minimum_tier),['vip']);
});
test('Expired Premium and VIP: deny both endpoints',async()=>{
 for(const [id,tier] of [[104,'premium'],[105,'vip']]){
  fixture(id,tier,'active',new Date(NOW-86400000).toISOString());
  for(const action of ['premium_resources','vip_resources'])assert.equal((await request(id,action)).status,403);
 }
});
test('Inactive Premium/VIP: deny both endpoints',async()=>{
 for(const [id,tier] of [[106,'premium'],[107,'vip']]){
  fixture(id,tier,'inactive');for(const action of ['premium_resources','vip_resources'])assert.equal((await request(id,action)).status,403);
 }
});
test('Null expiration follows current production policy: active VIP allowed',async()=>{
 fixture(108,'vip','active',null);assert.equal((await request(108,'vip_resources')).status,200);
});
test('Refund lifecycle simulation: entitlement recalculated to Free, then denied',async()=>{
 // This simulates the post-refund membership state, NOT the payment webhook/RPC.
 fixture(109,'vip');assert.equal((await request(109,'vip_resources')).status,200);
 fixture(109,'free');assert.equal((await request(109,'vip_resources')).status,403);
 assert.equal((await request(109,'premium_resources')).status,403);
});
test('VIP downgrade to Premium: VIP denied but Premium allowed',async()=>{
 fixture(110,'vip');assert.equal((await request(110,'vip_resources')).status,200);
 fixture(110,'premium');assert.equal((await request(110,'vip_resources')).status,403);
 assert.equal((await request(110,'premium_resources')).status,200);
});
test('Unknown action rejected',async()=>{
 fixture(111,'vip');assert.equal((await request(111,'refund_subscription')).status,400);
});
test('Uninitialized account returns 404',async()=>{
 assert.equal((await request(999,'premium_resources')).status,404);
});
