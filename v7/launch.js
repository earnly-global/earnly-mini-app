/* Earnly V7 additive launch candidate. No payment calls or privilege grants. */
(()=>{'use strict';
 const ID='earnly-v7-launch';
 const config={discovery:'https://byywbcwdhtiylexvqokj.supabase.co/functions/v1/earnly-discovery',origin:'https://earnly-global.github.io'};
 function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
 function safeStatus(){const tg=window.Telegram?.WebApp;return {telegram:!!tg?.initData,secure:location.protocol==='https:',discoveryConfigured:config.discovery.startsWith('https://'),paymentVerified:false};}
 function addPanel(){if(document.getElementById(ID))return;const profile=document.getElementById('profile');if(!profile)return;
 const box=el('section',undefined,'plan');box.id=ID;box.setAttribute('aria-label','Earnly V7 launch information');
 box.append(el('h3','🚀 Earnly V7 — Launch information'));
 box.append(el('p','Explore free listings. Premium offers server-protected discovery and matching; VIP adds comparison tools. Availability, eligibility and payouts are not guaranteed.'));
 const status=el('p','', 'notice');status.id='earnly-v7-status';box.append(status);
 const refresh=el('button','Check connection','secondary');refresh.type='button';refresh.addEventListener('click',()=>{const s=safeStatus();status.textContent=s.telegram?'Telegram session detected. Paid access is verified by Supabase on each protected request.':'Open Earnly from its Telegram bot to use account and paid features.';});box.append(refresh);
 const note=el('p','Purchases are not open until a real Telegram Stars payment and refund/cancellation lifecycle pass final verification. Never share Telegram sign-in data or payment credentials.','notice');box.append(note);
 const help=el('p','Subscription management: Telegram Settings → Stars → Subscriptions (menu labels may vary). Contact @EarnlyGlobalBot for support.','notice');box.append(help);
 profile.append(box);refresh.click();
 }
 function ready(){addPanel();}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ready,{once:true});else ready();
 window.EarnlyV7=Object.freeze({version:'7.0.0-rc1',getStatus:safeStatus});
})();
