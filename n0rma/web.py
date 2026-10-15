"""Local dashboard (http://127.0.0.1:8777). Calm grey theme by default (Night vision and the original Classic look selectable), a plain-words event timeline with resolve marks, Rebaseline and the evidence export."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>N0RMA</title><style>
:root{--bg:#121212;--fg:#f2f2f2;--mut:#c4c4c4;--faint:#8f8f8f;--card:#1e1e1e;--ring:#3a3a3a;
--okbg:#1e2b22;--watchbg:#2e2716;--alertbg:#331b1b;--offbg:#262626;--ok:#5cb874;--watch:#ffb347;--alert:#e5534b;--off:#9e9e9e;--btn:#2e2e2e;--btnfg:#fff;--link:#8ab4f8}
html.night{--bg:#000;--fg:#8c3030;--mut:#722b2b;--faint:#5a2222;--card:#0c0404;--ring:#2a0d0d;--okbg:#0c0404;--watchbg:#0c0404;--alertbg:#0c0404;--offbg:#0c0404;
--ok:#6e2a2a;--watch:#8c3434;--alert:#aa4040;--off:#4a1c1c;--btn:#1a0707;--btnfg:#8c3030;--link:#8c3030}
html.executive{--bg:#0e1116;--fg:#e6edf3;--mut:#9da7b3;--faint:#6e7681;--card:#161b22;--ring:#30363d;--okbg:#14231b;--watchbg:#2a2312;--alertbg:#2e1719;--offbg:#161b22;--ok:#58a6ff;--watch:#e3b341;--alert:#f85149;--off:#8b949e;--btn:#21262d;--btnfg:#e6edf3;--link:#58a6ff}
html.classic{--bg:#000;--fg:#a8e6b8;--mut:#6fa381;--faint:#4d7a5c;--card:rgba(2,14,7,.8);--ring:#14502f;--okbg:rgba(0,45,22,.55);--watchbg:rgba(52,36,0,.6);--alertbg:rgba(60,8,8,.65);--offbg:rgba(10,24,16,.6);--ok:#35e07a;--watch:#ffb000;--alert:#ff3b3b;--off:#5f8a70;--btn:#0a2a18;--btnfg:#5dff9a;--link:#5dff9a}
html{background:var(--bg)}body{margin:0;padding:16px;background:transparent;color:var(--fg);font:15px/1.45 -apple-system,'Segoe UI',system-ui,Roboto,'Helvetica Neue',Arial,sans-serif;max-width:1100px;margin:auto;position:relative;z-index:1}
html.classic body{font:15px ui-monospace,'SF Mono',Menlo,Consolas,monospace;max-width:900px}
.top{display:flex;align-items:center;gap:10px;margin:0 0 10px}.top h1{font-size:20px;margin:0;flex:1;font-weight:600}
select{font-size:13px;padding:5px 8px;border-radius:8px;border:1px solid var(--ring);background:var(--card);color:var(--fg)}
.dot{width:10px;height:10px;border-radius:50%;background:var(--off);display:inline-block}.dot.live{background:var(--ok);animation:br 1.4s ease-in-out infinite alternate}
@keyframes br{from{opacity:.3}to{opacity:1}}@media(prefers-reduced-motion:reduce){.dot.live{animation:none}}
.banner{border-radius:14px;padding:16px 18px;margin:8px 0;border-left:5px solid var(--off);background:var(--offbg)}
.banner b{font-size:20px;display:block}.banner span{font-size:13px;color:var(--mut)}
.tile{border-radius:12px;padding:12px 16px;margin:8px 0;border-left:5px solid var(--off);background:var(--offbg)}
.tile b{font-size:16px;display:block}.tile span{font-size:13px;color:var(--mut);word-break:break-word}
.ok{background:var(--okbg);border-color:var(--ok)}.ok b,.banner.ok b{color:var(--ok)}
.watch{background:var(--watchbg);border-color:var(--watch)}.watch b,.banner.watch b{color:var(--watch)}
.alert{background:var(--alertbg);border-color:var(--alert)}.alert b,.banner.alert b{color:var(--alert)}
.off b{color:var(--off)}
.card{background:var(--card);border-radius:14px;padding:14px 18px;margin:14px 0}.card h2{font-size:15px;margin:0 0 8px;color:var(--mut)}
table{width:100%;border-collapse:collapse;font-size:13px}td{padding:5px 6px;border-bottom:1px solid var(--ring)}
button{font-size:15px;padding:10px 16px;border-radius:10px;border:0;background:var(--btn);color:var(--btnfg);cursor:pointer}
button.s{font-size:12px;padding:4px 10px}label.n{font-size:13px;color:var(--mut);cursor:pointer}
.tabs{display:flex;gap:6px;margin:6px 0}.tabs button{flex:1;font-size:14px;padding:8px 4px;background:var(--card);color:var(--faint)}.tabs button.on{background:var(--btn);color:var(--btnfg)}.e-alert{color:var(--alert)}.e-watch{color:var(--watch)}.m{color:var(--mut)}a{color:var(--link)}
/* calm home */
.grid{display:grid;grid-template-columns:minmax(0,1fr) 250px;gap:18px;align-items:start}@media(max-width:820px){.grid{grid-template-columns:1fr}}
aside{position:sticky;top:12px}aside .card{margin-top:8px}aside button,aside a button{display:block;width:100%;margin:6px 0;text-align:left}
.cards3{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0}.cards3 .card{margin:0;padding:12px 14px}.cards3 h3{margin:0;font-size:12px;font-weight:500;color:var(--mut)}
.big{font-size:26px;font-weight:600;margin:2px 0}.chips{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}.chips button{padding:6px 14px;border-radius:20px;font-size:14px;background:var(--card);color:var(--fg)}.chips button.on{background:var(--ok);color:#0b1a10}
.evi{border-radius:12px;padding:12px 16px;margin:8px 0;background:var(--card)}.evi .h{font-size:13px;font-weight:600}.evi.done{opacity:.5}.evi.done .msg{text-decoration:line-through}
.evi .msg{margin:2px 0;word-break:break-word}.evi button.s{background:transparent;color:var(--link);padding:2px 0}
html.classic .calm-only,html:not(.classic) .classic-only,html:not(.classic) #rain,html:not(.classic) .defcon{display:none}
html.executive .calm-only,html:not(.executive) .exec-only{display:none}
.exec-only{max-width:680px;margin:18px auto}.exec-only .xh{font-size:42px;font-weight:300;margin:6px 0}.exec-only hr{border:0;border-top:1px solid var(--ring);margin:20px 0}
.exec-only .xl{display:block;padding:10px 0;font-size:16px;color:var(--link);text-decoration:none;cursor:pointer;background:none;border:0;text-align:left;width:100%}.exec-only .xk{font-size:12px;letter-spacing:.1em;color:var(--faint)}
.exec-only .xe{margin:12px 0}.exec-only .xe .h{font-size:13px;font-weight:600}.exec-only button.s{background:transparent;color:var(--link);padding:2px 0}
/* classic (the original look) */
html.classic #rain{position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:.22;transition:opacity .6s}
html.classic body::after{content:'';position:fixed;inset:0;z-index:5;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(0,0,0,.22) 0,rgba(0,0,0,.22) 1px,transparent 1px,transparent 3px);opacity:.35}
html.classic .card,html.classic .banner,html.classic .tile{border:1px solid var(--ring);backdrop-filter:blur(2px)}html.classic .banner,html.classic .tile{border-left-width:5px}
html.classic .card{position:relative;border-radius:2px;box-shadow:inset 0 0 24px rgba(0,255,110,.04)}
html.classic .card::before,html.classic .card::after{content:'';position:absolute;width:12px;height:12px;border:2px solid var(--ok);pointer-events:none}
html.classic .card::before{top:-2px;left:-2px;border-right:0;border-bottom:0}html.classic .card::after{bottom:-2px;right:-2px;border-left:0;border-top:0}
html.classic .banner,html.classic .tile{border-radius:2px}html.classic button{border-radius:2px;border:1px solid var(--ring);text-transform:uppercase;letter-spacing:.06em;font-family:inherit}
html.classic .card h2,html.classic .tabs button{text-transform:uppercase;letter-spacing:.08em}html.classic .top h1{letter-spacing:.3em;text-shadow:0 0 10px var(--ok);color:var(--ok)}
.defcon{display:flex;align-items:center;gap:8px;border:1px solid var(--ring);padding:4px 10px;background:var(--card);font-size:12px;letter-spacing:.12em}
.defcon .seg{display:flex;gap:3px}.defcon .seg i{font-style:normal;width:22px;height:22px;line-height:22px;text-align:center;font-size:13px;border:1px solid var(--ring);color:var(--faint)}
.defcon .seg i.on{color:#000;font-weight:bold;box-shadow:0 0 12px currentColor}
.defcon.d1 .seg i.on{animation:dc 0.7s steps(2) infinite}@keyframes dc{50%{opacity:.35}}
@media(prefers-reduced-motion:reduce){.defcon.d1 .seg i.on{animation:none}}
html.norain #rain{display:none}
</style><canvas id=rain></canvas><div class=top><span class=dot id=hb></span><h1>N0RMA <span class=m id=tbar></span> <span class=m id=t style="font-size:12px"></span></h1><div class=defcon id=defcon title="Alert level from N0RMA's own detectors (5 = all clear, 1 = confirmed alert)"><span>DEFCON</span><span class=seg><i>5</i><i>4</i><i>3</i><i>2</i><i>1</i></span></div><label class="n classic-only"><input type=checkbox id=rainT checked> Rain</label> <select id=themeSel title="Theme"><option value=calm>Calm</option><option value=night>Night vision</option><option value=executive>Executive</option><option value=classic>Classic</option></select></div>
<div class=tabs id=tabs><button data-t=status>Status</button><button data-t=nearby>Nearby</button><button data-t=radar>Radar</button><button data-t=history>History</button><button data-t=settings>Settings</button><button data-t=smart>Smart</button></div>
<div data-tab=status><div class=exec-only><div class=xh id=xhead></div><div id=xsub class=m style="font-size:16px"></div><hr>
<div class=xk>NEEDS A DECISION</div><div id=xlist></div><hr><div id=xrb></div><hr>
<a class=xl href="/api/evidence" download="n0rma-evidence.txt">Export evidence report</a>
<button class=xl onclick="showTab('settings')">Settings</button>
<button class=xl onclick="showTab('history');document.getElementById('safety').open=true">Safety checklist</button>
<p class=m style="font-size:12px">Detect-only. A quiet screen is not a guarantee of safety. Nothing leaves this computer except the optional address lookup in Settings.</p></div>
<div class=calm-only><div class=grid><main>
<div id=cbanner class=banner><b>Starting...</b></div>
<div class=cards3>
<div class=card><h3>Active scans</h3><div class=big id=c_scan>-</div><div class=m id=c_scan2 style="font-size:12px"></div></div>
<div class=card><h3>Detectors unresolved</h3><div class=big id=c_open>-</div><div class=m id=c_open2 style="font-size:12px"></div></div>
<div class=card><h3>Evidence reports</h3><div class=big id=c_evi>-</div><div class=m style="font-size:12px"><a href="/api/evidence" download="n0rma-evidence.txt">Export report</a></div></div>
</div>
<div class=card id=rbcard></div>
<h2 style="font-size:20px;margin:18px 0 4px">Events</h2>
<div class=chips id=chips></div><div id=tl></div>
<h2 style="font-size:20px;margin:22px 0 4px">Detectors</h2><div id=ctiles></div>
<div class=card><h2>Evidence export</h2><p style="font-size:14px;color:var(--mut)">Makes a plain-text report of everything flagged in the last 30 days. Each entry is linked to the one before it by a cryptographic hash, so any later edit, deletion or reordering breaks the chain and can be detected. Save the last line (the chain end) somewhere separate. Nothing is sent anywhere unless you send it.</p>
<a href="/api/evidence" download="n0rma-evidence.txt"><button>Export evidence report</button></a></div>
<p class=m style="font-size:12px">Detect-only. A quiet screen is not a guarantee of safety. Nothing leaves this computer except the optional address lookup in Settings.</p>
</main><aside><div class=card><h2>Quick actions</h2>
<a href="/api/evidence" download="n0rma-evidence.txt"><button>Export evidence</button></a>
<button onclick="rbAsk(true);document.getElementById('rbcard').scrollIntoView({behavior:'smooth'})">Rebaseline</button>
<button onclick="showTab('settings')">Settings</button>
<button onclick="showTab('history');document.getElementById('safety').open=true">Safety checklist</button>
</div></aside></div></div>
<div class=classic-only><div class=card id=welcome style="display:none"><b style="font-size:16px">Welcome - here's how this works</b>
<p style="font-size:13px;color:var(--mut);line-height:1.5">1. N0RMA is already scanning in the background. The banner below tells you in plain words if everything is normal - a breathing dot and live counts are proof it's working.<br>
2. Use Nearby to see every Wi-Fi network and Bluetooth device in range.<br>
3. Use Settings to set your home location (for the drone map and distances) and see your known Wi-Fi networks.<br>
4. Everything stays on this computer except the optional address lookup in Settings. Use the theme menu at the top for a calm, night-vision or classic look.</p>
<button class=s onclick="document.getElementById('welcome').style.display='none';try{localStorage.setItem('hw_welcomed','1')}catch(e){}">Got it</button></div>
<div id=banner class=banner><b>Starting...</b></div><div id=tiles></div><div id=trk></div><div id=camq></div>
<p><button onclick="fetch('/api/beep',{method:'POST',headers:{'X-Homewatch':'1'}}).then(load)">I heard the sensor beep - log it now</button></p>
</div></div>
<div data-tab=radar><div class=card><h2>Proximity radar <span class=m id=rstat>RANGE ONLY</span> <button class=s id=rhelpb onclick="rhelp.style.display=rhelp.style.display?'':'none'">?</button></h2>
<p id=rhelp class=m style="display:none;font-size:12px">Distance is estimated from signal strength and can be off indoors. This computer has no compass, so contacts are listed in the lane under the scope (nearer to the left, farther to the right): their position shows distance only, never direction. The Android app can measure a real direction: tap a contact and turn in place. The sweep beam is decoration.</p>
<canvas id=radar width=640 height=770 style="width:100%;max-width:560px;display:block;margin:auto"></canvas>
<p class=m style="font-size:12px;text-align:center">DIST: ESTIMATED FROM SIGNAL &middot; BEARING: UNKNOWN &nbsp; green = your network &nbsp; gray = neighbors &nbsp; amber = tracker/watch &nbsp; red = alert &nbsp; triangle = drone</p></div>
<div class=card id=dmapcard style="display:none"><h2>Drone map <span class=m>(real positions from Remote ID)</span></h2>
<canvas id=dmap width=640 height=480 style="width:100%;max-width:560px;display:block;margin:auto"></canvas><div id=dinfo class=m style="font-size:13px"></div></div>
</div>
<div data-tab=history>
<div class=card><h2>Evidence for police or an advocate</h2>
<p style="font-size:12px;color:var(--mut)">Makes a plain-text report of everything flagged (30 days) with a tamper-evident hash chain. You choose where to send it; nothing is sent automatically. The Android app makes the same format, and each can verify the other's reports.</p>
<a href="/api/evidence" download="n0rma-evidence.txt"><button>Export evidence report</button></a></div>
<details class=card id=safety><summary><b>Digital safety checklist (accounts, location sharing, stalkerware)</b></summary><div style="font-size:14px;line-height:1.5">
<p><b>First, safety:</b> if someone controls or watches your devices, removing their access can alert them. If you may be in danger, talk to an advocate before changing anything (US: National Domestic Violence Hotline 1-800-799-7233, or text START to 88788; tech-safety help at techsafety.org), and use a device they have never touched for sensitive steps.</p>
<p><b>Google account:</b> on a trusted device open myaccount.google.com &gt; Security &gt; Your devices and Recent security activity, and sign out anything you don't know. In Google Maps &gt; Location sharing, stop sharing with anyone you don't recognize.</p>
<p><b>Apple account:</b> Settings &gt; [your name] lists every signed-in device. In Find My &gt; People, stop sharing locations you don't want shared.</p>
<p><b>Family and carrier sharing:</b> check Family Sharing, Google Family Link, and your phone carrier's family locator service for anyone who can see where you are.</p>
<p><b>Passwords and email:</b> change passwords from a trusted device, turn on 2-step verification, and check your email for forwarding rules and recovery numbers/emails you didn't add.</p>
<p><b>On this computer:</b> check for unfamiliar remote-access tools or startup programs; N0RMA's own "This computer" tile already watches for new listening ports and remote-access software.</p>
<p><b>More help:</b> the Coalition Against Stalkerware (stopstalkerware.org) explains the signs and what to do.</p>
</div></details>
<div class=card><h2>Recent events</h2><table id=ev></table></div></div>
<div data-tab=status>
<details class=card><summary><b>If something is flagged - what to do</b></summary><div style="font-size:14px;line-height:1.5">
<p><b>Stay calm.</b> Most alerts turn out to be ordinary: a neighbor's device, your own phone, a passing car. A single amber or red line is a reason to look, not proof that someone is targeting you.</p>
<p><b>Tracker:</b> a tracker that stays strong for many minutes is worth finding. Use <code>n0rma find &lt;address&gt;</code> to walk toward it. Don't move or destroy it yet: photograph it where it is, note the time, and contact local law enforcement. iPhone: Find My &rarr; Items &rarr; Identify Found Item. Android: Settings &rarr; Safety &amp; emergency &rarr; Unknown tracker alerts.</p>
<p><b>Drone:</b> a Remote ID broadcast only <i>claims</i> a drone and can be faked. Note the time and what you saw. Don't shoot at, jam or interfere with it (that is a federal crime). You can report it to local law enforcement or the FAA.</p>
<p><b>Unknown device on your Wi-Fi:</b> look it up in your router's client list, block it, then change the Wi-Fi password and turn off WPS and any guest network you don't use.</p>
<p><b>If you feel unsafe</b> (for example a stalker or abusive partner), contact local police or the National Domestic Violence Hotline (US: 1-800-799-7233). A quiet dashboard is not a guarantee of safety: this tool cannot see every kind of device.</p>
</div></details></div>
<div data-tab=settings>
<div class=card><h2>Home location</h2>
<p style="font-size:12px;color:var(--mut)">Used for the drone map and for "X m from home" distances. Only the optional address search below leaves this computer (a one-time lookup); nothing else does.</p>
<p id=homeNow style="font-size:13px"></p>
<p style="font-size:12px;color:var(--mut)">Search by address:</p>
<input id=addrQ type=text placeholder="Street address, city, state" style="width:70%;padding:8px;border-radius:6px;border:1px solid var(--ring);background:var(--card);color:var(--fg)">
<button class=s onclick="geocode()">Search</button>
<div id=addrResults></div>
<p style="font-size:12px;color:var(--mut);margin-top:10px">Or type the numbers yourself (west longitude is negative, e.g. 40.7128, -74.0060):</p>
<input id=latT type=text placeholder="Latitude" style="width:120px;padding:8px;border-radius:6px;border:1px solid var(--ring);background:var(--card);color:var(--fg)">
<input id=lonT type=text placeholder="Longitude" style="width:120px;padding:8px;border-radius:6px;border:1px solid var(--ring);background:var(--card);color:var(--fg)">
<button class=s onclick="saveLatLon()">Save these numbers</button>
<button class=s onclick="post('/api/home?clear=1').then(()=>loadHome())">Clear home location</button>
</div>
<div class=card><h2>Your Wi-Fi networks</h2>
<p style="font-size:12px;color:var(--mut)">Marked "this is my network" on the Nearby tab; they show green on the radar.</p>
<div id=mySsids></div>
</div>
<div class=card><p style="font-size:11px;color:var(--faint)">N0RMA - detect-only. Nothing leaves this computer except the optional address lookup above. Formerly called Homewatch.</p></div>
</div>
<div data-tab=smart><div class=card><h2>Smart devices and privacy</h2>
<p style="font-size:12px;color:var(--mut)">Gadgets that listen, watch or share your connection, sorted by network name, Bluetooth name and maker. A name match is a hint, not proof; a device that hides its name won't show up here.</p>
<div id=smartlist></div></div>
<details class=card><summary><b>Privacy checklist (Sidewalk, Ring/Alexa, microphones, router)</b></summary><div style="font-size:14px;line-height:1.5">
<p><b>Amazon Sidewalk:</b> Alexa app &gt; More &gt; Settings &gt; Account Settings &gt; Amazon Sidewalk &gt; turn it off. Sidewalk lets Echo and Ring devices share part of your internet connection with nearby Amazon devices. Menu names change between app versions.</p>
<p><b>Ring and Alexa accounts:</b> in the Ring app open Control Center and review Shared Users and Authorized Client Devices; in the Alexa app open Alexa Privacy to review and delete voice history.</p>
<p><b>Microphones and cameras:</b> use the mute button on speakers when you don't need them, keep them out of bedrooms, cover or unplug cameras you aren't using.</p>
<p><b>Your router:</b> look through its connected-devices list, put smart gadgets on a guest network, change default passwords, install firmware updates.</p>
</div></details>
<div class=card><h2>License-plate cameras</h2>
<p style="font-size:12px;color:var(--mut)">DeFlock is a community map of automatic license-plate readers (such as Flock cameras), built on OpenStreetMap. This link opens it in your browser; N0RMA itself sends nothing, and the map site sees your visit like any website.</p>
<a href="https://maps.deflock.org" target=_blank rel="noopener noreferrer"><button>Open the DeFlock map</button></a></div></div>
<div data-tab=nearby><div class=card id=findcard style="display:none"></div><div class=card><h2>Wi-Fi networks nearby</h2><table id=wifi></table></div>
<div class=card><h2>Devices on your network</h2><table id=lan></table></div>
<div class=card><h2>Bluetooth trackers / drones in range</h2><table id=ble></table></div></div>
<script>
function setTheme(t){if(!['calm','night','executive','classic'].includes(t))t='calm';const h=document.documentElement;h.classList.toggle('night',t==='night');h.classList.toggle('executive',t==='executive');h.classList.toggle('classic',t==='classic');themeSel.value=t;try{localStorage.setItem('n0rma_theme',t)}catch(e){}try{if(LAST)drawRadar(LAST)}catch(e){}}
let TH='calm';try{TH=new URLSearchParams(location.search).get('theme')||localStorage.getItem('n0rma_theme')||(localStorage.getItem('hw_night')==='1'?'night':'calm')}catch(e){}
setTheme(TH);themeSel.onchange=()=>setTheme(themeSel.value);
function showTab(t){document.querySelectorAll('[data-tab]').forEach(e=>e.style.display=e.dataset.tab===t?'':'none');
 document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));try{localStorage.setItem('hw_tab',t)}catch(e){}}
document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>showTab(b.dataset.t));
let T0='status';try{T0=localStorage.getItem('hw_tab')||'status'}catch(e){}showTab(['status','nearby','radar','history','settings'].includes(T0)?T0:'status');
try{if(localStorage.getItem('hw_welcomed')!=='1')document.getElementById('welcome').style.display=''}catch(e){document.getElementById('welcome').style.display=''}
async function nameDev(mac,cur){const v=prompt('Name for this device (blank clears it):',cur||'');if(v===null)return;await post('/api/label?mac='+mac+'&label='+encodeURIComponent(v.trim()))}
const post=async u=>{await fetch(u,{method:'POST',headers:{'X-Homewatch':'1'}});load()};
async function loadHome(){const d=LAST||await (await fetch('/api/status')).json();
 document.getElementById('homeNow').innerHTML=d.home?('Set: '+d.home.lat.toFixed(5)+', '+d.home.lon.toFixed(5)+' - <a href="https://www.google.com/maps?q='+d.home.lat+','+d.home.lon+'&z=17'+'" target=_blank>view on map</a>'):'Not set.';
 document.getElementById('mySsids').innerHTML=(d.my_ssids||[]).length?(d.my_ssids||[]).map(s=>`<div>${E(s)} <button class=s onclick="post('/api/mynet?on=0&ssid='+encodeURIComponent(this.dataset.s))" data-s="${E(s).replace(/"/g,'&quot;')}">not mine</button></div>`).join(''):'<span class=m>none yet</span>'}
async function geocode(){const q=document.getElementById('addrQ').value.trim();if(!q)return;
 document.getElementById('addrResults').innerHTML='<span class=m>Searching...</span>';
 const r=await fetch('/api/geocode?q='+encodeURIComponent(q));const j=await r.json();
 if(!j.results||!j.results.length){document.getElementById('addrResults').innerHTML='<span class=m>No results.</span>';return}
 document.getElementById('addrResults').innerHTML=j.results.map(x=>`<div style="margin:6px 0">${E(x.name)}<br><button class=s onclick="saveHome(${x.lat},${x.lon})">Use this</button></div>`).join('')}
async function saveHome(lat,lon){await post('/api/home?lat='+lat+'&lon='+lon);loadHome()}
function saveLatLon(){const lat=parseFloat(document.getElementById('latT').value),lon=parseFloat(document.getElementById('lonT').value);
 if(isNaN(lat)||isNaN(lon)){alert('Enter both numbers.');return}saveHome(lat,lon)}
const ICON={ok:'✓',watch:'◔',alert:'▲',off:'–'};
const ago=s=>s<60?Math.round(s)+'s':Math.floor(s/60)+'m '+Math.round(s%60)+'s';
function banner(d){const lv=Object.values(d.state).filter(x=>x.title.indexOf('computer')<0).map(x=>x.level);const w=lv.includes('alert')?'alert':lv.includes('watch')?'watch':'ok';
 const b=document.getElementById('banner');b.className='banner '+w;hb.className='dot live';
 const wa=d.live.wifi_at?' · Wi-Fi: '+(d.live.wifi||[]).length+' networks (scanned '+ago(d.now-d.live.wifi_at)+' ago)':'';
 const ads=d.live.ble?' · Bluetooth: '+d.live.ble.advertisements_seen+' signals heard':'';
 b.innerHTML='<b>'+(w==='alert'?'Needs your attention':w==='watch'?'Keeping an eye on something':'All clear')+'</b><span>Scanning for '+ago(d.now-(d.started||d.now))+wa+ads+'</span>'}
const E=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let LAST=null,MY=new Set();
let FIND=null,BEST={};
function findW(k){FIND={t:'w',k:k};showTab('nearby');load()}
function findB(k){FIND={t:'b',k:k};showTab('nearby');load()}
async function mineW(k){await fetch('/api/minewifi?on=1&key='+encodeURIComponent(k),{method:'POST',headers:{'X-Homewatch':'1'}});load()}
function drawFind(d){const c=document.getElementById('findcard');if(!FIND){c.style.display='none';return}
 let h=[],label='',now=null;
 if(FIND.t==='w'){const r=(d.live.wifi||[]).find(x=>x.bssid===FIND.k);h=(d.live.wifi_hist||{})[FIND.k]||[];label=r?(r.ssid||'(hidden)')+' '+r.bssid:FIND.k;now=r?r.signal:null}
 else{const bb=d.live.ble||{trackers:[],drones:[]};const r=[...bb.trackers,...bb.drones].find(x=>String(x.addr)===FIND.k);h=r?(r.hist||[]):[];label=r?r.label+' '+r.addr:FIND.k;now=r?r.rssi:null}
 c.style.display='block';const best=h.length?Math.max(...h):null,key=FIND.t+FIND.k;if(best!==null)BEST[key]=Math.max(BEST[key]??-999,best);
 const slope=h.length>=4?(h.slice(-2).reduce((a,b)=>a+b)/2-h.slice(-4,-2).reduce((a,b)=>a+b)/2):0;
 const trend=h.length<4?'Walk a few steps, then wait for the next reading.':slope>1.5?'&#9650; Getting WARMER - keep going this way.':slope<-1.5?'&#9660; Getting COLDER - turn around.':'&#9679; No real change yet.';
 const word=now===null?'Not heard right now':now>=-50?'very hot: it is right here':now>=-62?'hot':now>=-75?'warm':'cold';
 c.innerHTML=`<h2>Finding: ${E(label)}</h2><canvas id=fcv width=640 height=140 style="width:100%;max-width:640px"></canvas><div style="font-size:14px;margin:6px 0"><b>${now===null?'-':Math.round(now)+' dBm'}</b> - ${word}. ${trend}</div><div class=m style="font-size:12px">Best so far: ${BEST[key]!==undefined?Math.round(BEST[key])+' dBm':'-'}. Wi-Fi refreshes about every 20 s and Bluetooth every few seconds. Walk slowly; the spot where it is loudest is the best clue. Don't remove anything you find: photograph it first.</div><button class=s onclick="FIND=null;load()">Close</button>`;
 const cv=document.getElementById('fcv'),x=cv.getContext('2d'),W=cv.width,H=cv.height,dark=true;x.clearRect(0,0,W,H);x.strokeStyle='#2a2a2a';x.strokeRect(1,1,W-2,H-2);
 const Y=v=>H-((Math.max(-100,Math.min(-30,v))+100)/70)*H;if(BEST[key]!==undefined){x.setLineDash([8,6]);x.strokeStyle='#b39a55';x.beginPath();x.moveTo(0,Y(BEST[key]));x.lineTo(W,Y(BEST[key]));x.stroke();x.setLineDash([])}
 if(h.length>1){x.strokeStyle='#5e9a74';x.lineWidth=2;x.beginPath();h.forEach((v,i)=>{const px=i*(W/(h.length-1));i?x.lineTo(px,Y(v)):x.moveTo(px,Y(v))});x.stroke();x.fillStyle='#c06a6a';x.beginPath();x.arc(W,Y(h[h.length-1]),4,0,7);x.fill()}}
async function mine(a,on){await fetch('/api/mine?addr='+encodeURIComponent(a)+'&on='+on,{method:'POST',headers:{'X-Homewatch':'1'}});load()}
const C=()=>getComputedStyle(document.documentElement);
function hash(str){let h=0;for(let i=0;i<str.length;i++)h=(h*31+str.charCodeAt(i))>>>0;return h}
function rssiToM(r,tx){return Math.pow(10,(tx-r)/25)}   // log-distance, n=2.5 (rough, indoors)
function rpos(m){const R=[5,20,60];const mm=Math.max(.5,m);let f;
 if(mm<=5)f=mm/5*.33;else if(mm<=20)f=.33+(mm-5)/15*.33;else f=Math.min(1,.66+Math.min(mm-20,40)/40*.34);return f}
function blips(d){const L=d.live,out=[],mine=new Set(d.my_ssids||[]);
 (L.wifi||[]).forEach(w=>{const known=mine.has(w.ssid)||w.klass==='camera';
  out.push({id:w.bssid,label:w.ssid||'hidden',m:rssiToM(w.signal,-45),col:mine.has(w.ssid)?getComputedStyle(document.documentElement).getPropertyValue('--ok').trim():(w.klass==='camera'||w.klass==='drone')?'#ff3b3b':'#6f9a80'})});
 const b=L.ble||{trackers:[],drones:[]};
 b.trackers.forEach(t=>out.push({id:t.addr,label:t.label,m:rssiToM(t.rssi,-59),col:d.state.tracker.level==='alert'?'#ff3b3b':'#ffb000',pulse:1}));
 b.drones.forEach(t=>out.push({id:t.addr,label:'DRONE',m:rssiToM(t.rssi,-59),col:'#ff3b3b',tri:1,pulse:1}));
 return out}
const RM=matchMedia('(prefers-reduced-motion: reduce)').matches;
const DC_COL={5:'#35e07a',4:'#9be035',3:'#ffb000',2:'#ff6a00',1:'#ff3b3b'};
function defcon(state){const v=Object.entries(state||{}).filter(([k])=>k!=='host').map(([,x])=>x.level);
 if(!v.length||v.every(l=>l==='off'))return 0;
 const al=v.filter(l=>l==='alert').length,wa=v.filter(l=>l==='watch').length;
 if(state.drone&&state.drone.level==='alert'||al>=2)return 1;if(al===1)return 2;if(wa>=2)return 3;if(wa===1)return 4;return 5}
function drawDefcon(d){const n=defcon(d.state),el=document.getElementById('defcon');el.className='defcon'+(n?' d'+n:'');
 el.querySelectorAll('.seg i').forEach(i=>{const on=+i.textContent===n;i.className=on?'on':'';i.style.background=on?DC_COL[n]:'';i.style.color=on?'#000':''})}
(function(){const c=document.getElementById('rain'),x=c.getContext('2d'),G='ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789',FS=16;let cols=0,drops=[];
 function size(){c.width=innerWidth;c.height=innerHeight;cols=Math.ceil(c.width/FS);drops=Array.from({length:cols},()=>Math.random()*c.height/FS)}
 size();addEventListener('resize',size);
 function tick(){if(document.hidden||RM||!document.documentElement.classList.contains('classic')||document.documentElement.classList.contains('norain'))return;
  const night=document.documentElement.classList.contains('night'),radar=document.querySelector('[data-tab=radar]').style.display==='';
  c.style.opacity=night?.08:radar?.38:.2;
  x.fillStyle='rgba(0,0,0,.09)';x.fillRect(0,0,c.width,c.height);x.font=FS+'px monospace';
  for(let i=0;i<cols;i++){const ch=G[Math.floor(Math.random()*G.length)];
   x.fillStyle=Math.random()<.04?(night?'#aa4040':'#e0ffe8'):(night?'#6e2a2a':'#35e07a');x.fillText(ch,i*FS,drops[i]*FS);
   if(drops[i]*FS>c.height&&Math.random()>.975)drops[i]=0;drops[i]+=1}}
 setInterval(tick,60);
 let RN=true;try{RN=localStorage.getItem('hw_rain')!=='0'}catch(e){}
 const t=document.getElementById('rainT');t.checked=RN&&!RM;document.documentElement.classList.toggle('norain',!t.checked);
 t.onchange=()=>{document.documentElement.classList.toggle('norain',!t.checked);x.clearRect(0,0,c.width,c.height);try{localStorage.setItem('hw_rain',t.checked?'1':'0')}catch(e){}}})();
function radarAlpha(sweep,a,pulse){const dl=((sweep-a)%(2*Math.PI)+2*Math.PI)%(2*Math.PI);const f=.15+.85*Math.exp(-dl/1.7);return pulse?Math.max(.7,f):f}
function drawRadar(d){const c=document.getElementById('radar'),x=c.getContext('2d'),W=c.width,cx=W/2,R=W/2-30;
 x.clearRect(0,0,W,770);const night=document.documentElement.classList.contains('night');
 const cs=getComputedStyle(document.documentElement),G=cs.getPropertyValue('--ok').trim(),GD=cs.getPropertyValue('--ring').trim(),TX=cs.getPropertyValue('--mut').trim(),classic=document.documentElement.classList.contains('classic');
 const t=Date.now()/1000,sw=RM?-Math.PI/2:((t/4)%1)*2*Math.PI-Math.PI/2;
 // scope face
 const g=x.createRadialGradient(cx,cx,0,cx,cx,R);g.addColorStop(0,night?'rgba(30,6,6,.9)':classic?'rgba(0,52,24,.85)':'rgba(48,48,48,.9)');g.addColorStop(1,night||classic?'rgba(0,8,4,.92)':'rgba(24,24,24,.95)');
 x.fillStyle=g;x.beginPath();x.arc(cx,cx,R,0,7);x.fill();
 // rim ticks (decor only - no bearing data)
 x.strokeStyle=G;x.lineWidth=1;x.globalAlpha=.7;
 for(let i=0;i<36;i++){const a=i*Math.PI/18,l=i%3===0?14:7;x.beginPath();x.moveTo(cx+(R+4)*Math.cos(a),cx+(R+4)*Math.sin(a));x.lineTo(cx+(R+4+l)*Math.cos(a),cx+(R+4+l)*Math.sin(a));x.stroke()}
 // rings + crosshair
 x.globalAlpha=1;x.shadowColor=G;x.shadowBlur=8;x.strokeStyle=GD;x.lineWidth=1.5;x.fillStyle=TX;x.font='15px monospace';
 [[.33,'VERY CLOSE'],[.66,'CLOSE'],[1,'FAR']].forEach(([f,l])=>{x.beginPath();x.arc(cx,cx,R*f,0,7);x.stroke();x.fillText(l,cx+6,cx-R*f+17)});
 x.beginPath();x.moveTo(cx-R,cx);x.lineTo(cx+R,cx);x.moveTo(cx,cx-R);x.lineTo(cx,cx+R);x.stroke();x.shadowBlur=0;
 // sweep trail + beam
 if(!RM){for(let i=0;i<44;i++){x.fillStyle=G;x.globalAlpha=.26*Math.pow(1-i/44,2);x.beginPath();x.moveTo(cx,cx);x.arc(cx,cx,R,sw-(i+1)*.028,sw-i*.028);x.closePath();x.fill()}x.globalAlpha=1}
 x.strokeStyle=G;x.lineWidth=2;x.shadowColor=G;x.shadowBlur=10;x.beginPath();x.moveTo(cx,cx);x.lineTo(cx+R*Math.cos(sw),cx+R*Math.sin(sw));x.stroke();x.shadowBlur=0;
 // lane under the scope: no bearing exists on this computer, so contacts are placed by DISTANCE ONLY
 const bl=blips(d).sort((p,q)=>p.m-q.m),LY=660,LH=100;
 x.fillStyle='rgba(0,60,28,.12)';x.fillRect(10,LY,W-20,LH);x.strokeStyle=GD;x.lineWidth=1;x.setLineDash([8,6]);x.strokeRect(10,LY,W-20,LH);x.setLineDash([]);
 x.fillStyle='#ffb000';x.font='15px monospace';x.fillText('DIRECTION UNKNOWN',20,LY+20);x.fillStyle=TX;x.fillText('NEAR',W-120,LY+20);x.fillText('FAR >',W-64,LY+20);
 bl.forEach((p,i)=>{const px=24+(W-48)*rpos(p.m),row=i%3,py=LY+40+row*22,al=RM?1:(.7+.3*Math.sin(t*2+i));
  x.fillStyle=p.col;x.globalAlpha=al;x.shadowColor=p.col;x.shadowBlur=10*al;
  x.beginPath();if(p.tri){x.moveTo(px,py-9);x.lineTo(px+8,py+6);x.lineTo(px-8,py+6);x.closePath()}else x.arc(px,py,5,0,7);x.fill();x.shadowBlur=0;
  x.fillStyle=TX;x.font='13px monospace';const lab=(p.label||'').slice(0,12).toUpperCase(),lw=x.measureText(lab).width;x.fillText(lab,px+lw+14>W-12?px-lw-9:px+9,py+4);x.globalAlpha=1});
 if(!bl.length){x.fillStyle=TX;x.fillText('no contacts',20,LY+50)}
 // you
 x.shadowColor='#58a6ff';x.shadowBlur=14;x.fillStyle='#58a6ff';x.fillRect(cx-6,cx-6,12,12);x.shadowBlur=0;x.strokeStyle='#58a6ff';x.lineWidth=1;x.strokeRect(cx-11,cx-11,22,22);
 // readout
 const near=bl.length?Math.min(...bl.map(p=>p.m)):null;x.fillStyle=G;x.font='15px monospace';
 x.fillText('CONTACTS  '+bl.length,10,22);x.fillText('NEAREST   '+(near==null?'--':Math.round(near)+' M (EST)'),10,42);x.fillText('BEARING   N/A (NO COMPASS)',10,62)}
function toM(lat,lon,H){const k=111320;return [(lon-H.lon)*k*Math.cos(H.lat*Math.PI/180),(lat-H.lat)*k]}
function drawDrone(d){const fixes=[].concat(...Object.values(d.live.drone_fixes||{})).filter(f=>f.lat),H=d.home;
 const card=document.getElementById('dmapcard');if(!fixes.length||!H){card.style.display='none';return}
 card.style.display='block';const c=document.getElementById('dmap'),x=c.getContext('2d'),W=c.width,Hh=c.height;
 x.clearRect(0,0,W,Hh);const dark=matchMedia('(prefers-color-scheme: dark)').matches,txt=dark?'#7a7a7a':'#59636e';
 let pts=[];fixes.forEach(f=>{pts.push(toM(f.lat,f.lon,H));if(f.op_lat)pts.push(toM(f.op_lat,f.op_lon,H))});
 const maxd=Math.max(100,...pts.map(p=>Math.hypot(p[0],p[1])))*1.25,sc=Math.min(W,Hh)/2/maxd,cx=W/2,cy=Hh/2;
 x.strokeStyle=dark?'#30363d':'#c9d1d9';x.fillStyle=txt;x.font='16px sans-serif';
 [.25,.5,1].forEach(f=>{x.beginPath();x.arc(cx,cy,maxd*f*sc,0,7);x.stroke();x.fillText(Math.round(maxd*f)+' m',cx+4,cy-maxd*f*sc+16)});
 x.fillText('N',cx-5,18);x.fillStyle='#58a6ff';x.fillRect(cx-7,cy-7,14,14);x.fillStyle=txt;x.fillText('HOME',cx+10,cy+4);
 let info=[];fixes.forEach(f=>{const [mx,my]=toM(f.lat,f.lon,H),px=cx+mx*sc,py=cy-my*sc,dist=Math.round(Math.hypot(mx,my));
  const brg=Math.round((Math.atan2(mx,my)*180/Math.PI+360)%360);x.fillStyle='#da3633';x.beginPath();x.moveTo(px,py-12);x.lineTo(px+11,py+9);x.lineTo(px-11,py+9);x.closePath();x.fill();
  if(f.op_lat){const [ox,oy]=toM(f.op_lat,f.op_lon,H);x.fillStyle='#d29922';x.beginPath();x.arc(cx+ox*sc,cy-oy*sc,7,0,7);x.fill();x.strokeStyle='#d29922';x.beginPath();x.moveTo(px,py);x.lineTo(cx+ox*sc,cy-oy*sc);x.stroke()}
  info.push(`Drone ${E(f.id)}: ${dist} m ${['N','NE','E','SE','S','SW','W','NW'][Math.round(brg/45)%8]} of home, alt ${f.alt??'?'} m`+(f.op_lat?' (amber dot = operator)':'')+` - <a href="https://www.google.com/maps?q=${f.lat},${f.lon}&z=17" target=_blank>open in map</a>`)});
 dinfo.innerHTML=info.join('<br>')}
const LW=l=>l==='alert'?'Alert':l==='watch'?'Suspect':'Info';
const SW=l=>l==='ok'?'Clear':l==='off'?'Off':LW(l);
const isFlag=l=>l==='alert'||l==='watch';
let FILT='all',RB=false;
function setFilt(f){FILT=f;if(LAST)drawCalm(LAST)}
async function resolveEv(id,on){await post('/api/resolve?id='+id+'&on='+on)}
function rbAsk(v){RB=v;if(LAST)drawCalm(LAST)}
async function rbDo(){RB=false;await post('/api/rebaseline')}
async function rbReset(){await post('/api/rebaseline?clear=1')}
function drawCalm(d){
 const res=new Set(d.resolved||[]),evs=d.events||[];
 const st=Object.entries(d.state).filter(([k])=>k!=='host'),lv=st.map(([,x])=>x.level),on=lv.filter(l=>l!=='off').length;
 const open=evs.filter(e=>isFlag(e.level)&&!res.has(e.id)).length;
 const w=lv.includes('alert')?'alert':lv.includes('watch')?'watch':'ok';
 const head=!on?'Not scanning':w==='alert'?'Alert: look at this now':w==='watch'?'Something to check':'All clear';
 const b=document.getElementById('cbanner');b.className='banner '+(on?w:'off');
 b.innerHTML='<b>'+(on?ICON[w]:ICON.off)+' '+head+'</b><span>'+(open?open+(open===1?' item is':' items are')+' not yet resolved.':'Nothing needs your attention.')+'</span>';
 document.getElementById('tbar').textContent='· '+(w==='alert'?'Alert':w==='watch'?'Something to check':'All systems nominal');
 c_scan.textContent=on+' of '+lv.length;c_scan2.textContent='detectors running';
 c_open.textContent=open;c_open2.textContent=open?'review below':'none';
 c_evi.textContent=evs.length;
 const at=d.baseline_at;
 rbcard.innerHTML='<h2>Rebaseline</h2><p style="font-size:14px;color:var(--mut)">'+(at?'Locked in '+new Date(at*1000).toLocaleString()+'. Any new device on your network is flagged right away. Rebaseline again after you add or move your own devices.':'When everything looks normal and the devices shown are yours, tap Rebaseline. N0RMA locks them in, and anything new after that is flagged right away. Cameras stay watched either way.')+'</p>'
  +(RB?'<p style="font-size:14px"><b>Lock in what is here now?</b> Only do this if the devices N0RMA shows are yours. Network devices, listening ports and USB devices seen right now become normal. Camera-like devices, trackers and open items are not changed: decide about each one yourself.</p><button onclick="rbDo()">Yes, rebaseline</button> <button class=s onclick="rbAsk(false)">Cancel</button>'
   :'<button onclick="rbAsk(true)">Rebaseline</button>'+(at?' <button class=s onclick="rbReset()">Reset baseline</button>':''));
 const F=[['all','All'],['info','Info'],['watch','Suspect'],['alert','Alert']];
 chips.innerHTML=F.map(([k,l])=>`<button class="${FILT===k?'on':''}" onclick="setFilt('${k}')">${l}</button>`).join('');
 const shown=evs.filter(e=>FILT==='all'||(FILT==='info'?!isFlag(e.level):e.level===FILT)).slice(0,60);
 tl.innerHTML=shown.map(e=>{const done=res.has(e.id);return `<div class="evi${done?' done':''}"><div class=h style="color:${e.level==='alert'?'var(--alert)':e.level==='watch'?'var(--watch)':'var(--ok)'}">${LW(e.level)} · ${new Date(e.ts*1000).toLocaleString([], {weekday:'short',hour:'numeric',minute:'2-digit'})}</div><div class=msg>${E(e.msg)}</div>`+(isFlag(e.level)?`<button class=s onclick="resolveEv(${+e.id},${done?0:1})">${done?'Unresolve':'Mark resolved (my device / false alarm)'}</button>`:'')+'</div>'}).join('')||'<p class=m>Nothing here.</p>';
 ctiles.innerHTML=Object.values(d.state).map(s=>`<div class="tile ${s.level}"><b>${ICON[s.level]} ${SW(s.level)} · ${E(s.title)}</b><span>${E(s.msg)}</span></div>`).join('')}
function drawExec(d){
 const res=new Set(d.resolved||[]),evs=d.events||[],lv=Object.entries(d.state).filter(([k])=>k!=='host').map(([,x])=>x.level);
 const on=lv.some(l=>l!=='off'),open=evs.filter(e=>isFlag(e.level)&&!res.has(e.id));
 const w=lv.includes('alert')?'alert':(lv.includes('watch')||open.length)?'watch':'ok';
 xhead.textContent=!on?'Not scanning':w==='alert'?'Alert':w==='watch'?'Review needed':'All clear';
 xhead.style.color=!on?'var(--off)':'var(--'+w+')';
 xsub.textContent=open.length?open.length+(open.length===1?' open item.':' open items.'):'No open items.';
 xlist.innerHTML=open.slice(0,3).map(e=>`<div class=xe><div class=h style="color:${e.level==='alert'?'var(--alert)':'var(--watch)'}">${LW(e.level)} · ${new Date(e.ts*1000).toLocaleString([], {weekday:'short',hour:'numeric',minute:'2-digit'})}</div><div>${E(e.msg)}</div><button class=s onclick="resolveEv(${+e.id},1)">Mark resolved</button></div>`).join('')||'<p class=m>Nothing open.</p>';
 xrb.innerHTML=rbcard.innerHTML}
async function load(){try{const d=await (await fetch('/api/status')).json();LAST=d;MY=new Set(d.my_ssids||[]);drawRadar(d);drawDrone(d);
document.getElementById('t').textContent=new Date(d.now*1000).toLocaleTimeString();loadHome();
banner(d);drawDefcon(d);drawCalm(d);drawExec(d);tiles.innerHTML=Object.values(d.state).map(s=>`<div class="tile ${s.level}"><b>${ICON[s.level]} ${SW(s.level).toUpperCase()} · ${E(s.title)}</b><span>${E(s.msg)}</span></div>`).join('');
ev.innerHTML=d.events.map(e=>`<tr class="e-${e.level}"><td>${new Date(e.ts*1000).toLocaleTimeString()}</td><td>${LW(e.level)}</td><td>${e.domain}</td><td>${E(e.msg)}</td></tr>`).join('')||'<tr><td class=m>nothing yet</td></tr>';
wifi.innerHTML=(d.live.wifi||[]).map(w=>`<tr><td>${E(w.ssid)}</td><td>${w.bssid}</td><td>${w.signal} dBm</td><td>${E(w.vendor)}</td><td>${w.klass}</td><td><button class=s data-k="${w.bssid}" onclick="findW(this.dataset.k)">find</button></td><td>${w.ssid&&w.ssid!=='(hidden)'?(MY.has(w.ssid)?`<b>(yours)</b> <button class=s onclick="post('/api/mynet?on=0&ssid='+encodeURIComponent(this.dataset.s))" data-s="${E(w.ssid).replace(/"/g,'&quot;')}">not mine</button>`:`<button class=s onclick="post('/api/mynet?on=1&ssid='+encodeURIComponent(this.dataset.s))" data-s="${E(w.ssid).replace(/"/g,'&quot;')}">this is my network</button>`):''}</td></tr>`).join('');
lan.innerHTML=(d.live.lan||[]).map(w=>`<tr><td>${w.ip}</td><td>${w.label?`<b>${E(w.label)}</b>`:E(w.hostname)||'<span class=m>-</span>'} <button class=s onclick="nameDev('${w.mac}',this.dataset.n)" data-n="${E(w.label||w.hostname).replace(/"/g,'&quot;')}">name</button></td><td>${w.mac}</td><td>${E(w.vendor)}</td><td>${w.klass}${w.gateway?' (router)':''}</td><td>${Object.values(w.ports).join(',')}</td><td>${w.trusted?'<b>(known)</b> ':''}<button class=s onclick="post('/api/trust?on=${w.trusted?0:1}&mac=${w.mac}')">${w.trusted?'not known':'I know this device'}</button></td></tr>`).join('');
const sm=d.smart||{},GN=d.smart_names||{};
document.getElementById('smartlist').innerHTML=Object.keys(sm).map(g=>`<p><b>${E((GN[g]||[g])[0])} (${sm[g].length})</b><br><span class=m style="font-size:11px">${E((GN[g]||['',''])[1])}</span></p><table>`+sm[g].slice(0,12).map(r=>`<tr><td>${E(r.title)}</td><td>${E(r.sub)}</td><td>${E(String(r.signal))} dBm</td></tr>`).join('')+'</table>').join('')||'<p class=m style="font-size:13px">No recognisable smart devices heard yet. Wi-Fi refreshes every ~30 s.</p>';
const cq=d.live.cam;document.getElementById('camq').innerHTML=cq?`<div class=card><h2>Camera-like Wi-Fi source heard</h2><div style="font-size:13px">${E(cq.ssid||'(hidden)')} <span class=m>${E(cq.bssid)} · ${Math.round(cq.signal)} dBm</span> <button class=s data-k="${E(cq.key)}" onclick="mineW(this.dataset.k)">This is mine / known</button> <button class=s data-k="${E(cq.bssid)}" onclick="findW(this.dataset.k)">find it</button></div><p class=m style="font-size:11px">A match is a reason to look, not proof. Mark it only if you know what it is.</p></div>`:'';
drawFind(d);
const b0=d.live.ble||{trackers:[],drones:[]};
const dur=s=>s<90?s+' s':s<5400?Math.round(s/60)+' min':s<172800?Math.round(s/3600)+' h':Math.round(s/86400)+' days';
const unk=(b0.trackers||[]).filter(x=>!x.mine);
document.getElementById('trk').innerHTML=unk.length?'<div class=card><h2>Trackers heard nearby - are any of these yours?</h2>'+unk.map(x=>{const a=String(x.addr).replace(/[^0-9A-Fa-f:]/g,'');return `<div style="font-size:13px;margin:6px 0">${E(x.label)} <span class=m>${a} · ${x.rssi} dBm · here for ${dur(x.seen_s)}</span> <button class=s onclick="mine('${a}',1)">This is mine</button></div>`}).join('')+'<p class=m style="font-size:11px">Tap "This is mine" for your own Tile, AirTag or headphones so they stop being flagged. A tracker you do NOT recognise that stays close for hours is worth finding (n0rma find &lt;address&gt;).</p></div>':'';
const b=d.live.ble||{trackers:[],drones:[]};
ble.innerHTML=[...b.drones.map(x=>['DRONE',x]),...b.trackers.map(x=>['tracker',x])].map(([k,x])=>`<tr><td>${k}${x.mine?' <b>(yours)</b>':''}</td><td>${E(x.label)}</td><td>${x.addr}</td><td>${x.rssi} dBm <button class=s data-k="${String(x.addr).replace(/[^0-9A-Fa-f:]/g,'')}" onclick="findB(this.dataset.k)">find</button></td><td>${x.seen_s}s</td><td>${k==='tracker'?`<button class=s onclick="mine('${x.addr}',${x.mine?0:1})">${x.mine?'not mine':'this is mine'}</button>`:''}</td></tr>`).join('')||'<tr><td class=m>none</td></tr>';
}catch(e){}}
load();setInterval(load,2500);setInterval(()=>{if(LAST&&!document.hidden)drawRadar(LAST)},RM?500:50);</script>"""


from .core import clean  # noqa: E402


def serve(eng, host="127.0.0.1", port=8777, token=None):
    import hmac
    from http.cookies import SimpleCookie
    from urllib.parse import urlparse, parse_qs

    class H(BaseHTTPRequestHandler):
        def _host_ok(self):
            """Without a token (localhost mode) only accept Host: 127.0.0.1/localhost - blocks DNS rebinding."""
            if token:
                return True
            h = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
            return h in ("127.0.0.1", "localhost", "::1")

        def _authed(self):
            if not self._host_ok():
                return False
            if not token:
                return True
            q = parse_qs(urlparse(self.path).query).get("k", [""])[0]
            if hmac.compare_digest(q.encode(), token.encode()):
                return True
            try:
                ck = SimpleCookie(self.headers.get("Cookie", ""))
                v = ck["hw_k"].value if "hw_k" in ck else ""
            except Exception:
                v = ""
            return hmac.compare_digest(v.encode(), token.encode())

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            b = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            path = urlparse(self.path).path
            if not self._authed():
                return self._send(401, "Locked. Open the full link printed by n0rma (it ends in ?k=...).", "text/plain")
            if path == "/api/status":
                snap = eng.snapshot()
                try:
                    from . import smart
                    snap["smart"] = smart.group_live(snap.get("live", {}))
                    snap["smart_names"] = {k: list(v) for k, v in smart.GROUPS.items()}
                except Exception:
                    pass
                self._send(200, json.dumps(snap, default=str))
            elif path == "/api/evidence":
                from . import evidence
                from .core import clean
                rows = eng.db.query("SELECT ts,domain,level,msg FROM events WHERE ts>? ORDER BY ts", (__import__("time").time() - 30 * 86400,))
                text = evidence.build([dict(r, msg=clean(r["msg"], 400)) for r in rows]).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="n0rma-evidence.txt"')
                self.send_header("Content-Length", str(len(text)))
                self.end_headers()
                self.wfile.write(text)
            elif path == "/api/geocode":
                import urllib.request, urllib.parse
                q = parse_qs(urlparse(self.path).query).get("q", [""])[0][:200]
                if not q:
                    return self._send(400, '{"error":"empty"}')
                try:
                    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + urllib.parse.urlencode({"address": q, "benchmark": "Public_AR_Current", "format": "json"})
                    req = urllib.request.Request(url, headers={"User-Agent": "N0RMA home-counter-surveillance-tool (https://github.com/sloppytopp/n0rma)"})
                    raw = json.loads(urllib.request.urlopen(req, timeout=8).read())["result"]["addressMatches"][:5]
                    results = [{"name": r["matchedAddress"], "lat": float(r["coordinates"]["y"]), "lon": float(r["coordinates"]["x"])} for r in raw]
                except Exception:
                    results = []
                self._send(200, json.dumps({"results": results}))
            elif path == "/":
                b = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(b)))
                if token:
                    self.send_header("Set-Cookie", f"hw_k={token}; Path=/; Max-Age=31536000; SameSite=Strict; HttpOnly")
                self.end_headers()
                self.wfile.write(b)
            else:
                self._send(404, "{}")

        def do_POST(self):
            if not self._authed() or self.headers.get("X-Homewatch") != "1":
                return self._send(403, "{}")  # custom header forces a CORS preflight -> cross-site POSTs die
            if self.path.startswith("/api/mine"):
                q = parse_qs(urlparse(self.path).query)
                addr = (q.get("addr", [""])[0]).upper()
                if not re.fullmatch(r"[0-9A-F]{2}(:[0-9A-F]{2}){5}", addr):
                    return self._send(400, '{"error":"bad address"}')
                cur = set(eng.db.kv_get("ble_ignore", []))
                (cur.add if q.get("on", ["1"])[0] == "1" else cur.discard)(addr)
                eng.db.kv_set("ble_ignore", sorted(cur))
                return self._send(200, '{"ok":true}')
            if self.path.startswith("/api/minewifi"):
                q = parse_qs(urlparse(self.path).query)
                key = q.get("key", [""])[0]
                if not re.fullmatch(r"wifi:[0-9a-f]{2}(:[0-9a-f]{2}){4}\|[^\x00-\x1f]{0,32}", key):
                    return self._send(400, '{"error":"bad key"}')
                cur = set(eng.db.kv_get("wifi_mine", []))
                (cur.add if q.get("on", ["1"])[0] == "1" else cur.discard)(key)
                eng.db.kv_set("wifi_mine", sorted(cur))
                return self._send(200, '{"ok":true}')
            if self.path.startswith("/api/trust"):
                q = parse_qs(urlparse(self.path).query)
                mac = (q.get("mac", [""])[0]).lower()
                if not re.fullmatch(r"[0-9a-f]{2}(:[0-9a-f]{2}){5}", mac):
                    return self._send(400, '{"error":"bad mac"}')
                eng.db.exec("UPDATE devices SET trusted=? WHERE mac=?", (1 if q.get("on", ["1"])[0] == "1" else 0, mac))
                return self._send(200, '{"ok":true}')
            if self.path.startswith("/api/label"):
                q = parse_qs(urlparse(self.path).query)
                mac = (q.get("mac", [""])[0]).lower()
                label = q.get("label", [""])[0].strip()
                if not re.fullmatch(r"[0-9a-f]{2}(:[0-9a-f]{2}){5}", mac) or len(label) > 40 or label != clean(label, 40):
                    return self._send(400, '{"error":"bad name"}')
                eng.db.exec("UPDATE devices SET label=? WHERE mac=?", (label, mac))
                return self._send(200, '{"ok":true}')
            if self.path.startswith("/api/mynet"):
                from .core import load_config, save_config
                q = parse_qs(urlparse(self.path).query)
                ssid = q.get("ssid", [""])[0]
                if not ssid or ssid == "(hidden)" or len(ssid.encode()) > 32 or any(ord(c) < 32 for c in ssid):
                    return self._send(400, '{"error":"bad ssid"}')
                cfg = load_config()
                cur = set(cfg.get("my_ssids", []))
                (cur.add if q.get("on", ["1"])[0] == "1" else cur.discard)(ssid)
                cfg["my_ssids"] = sorted(cur)
                save_config(cfg)
                return self._send(200, '{"ok":true}')
            if self.path.startswith("/api/home"):
                from .core import load_config, save_config
                q = parse_qs(urlparse(self.path).query)
                cfg = load_config()
                if q.get("clear", ["0"])[0] == "1":
                    cfg.pop("home", None)
                else:
                    try:
                        lat, lon = float(q.get("lat", [""])[0]), float(q.get("lon", [""])[0])
                        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                            raise ValueError
                    except ValueError:
                        return self._send(400, '{"error":"bad coordinates"}')
                    cfg["home"] = {"lat": lat, "lon": lon}
                save_config(cfg)
                return self._send(200, '{"ok":true}')
            if self.path.startswith("/api/resolve"):
                q = parse_qs(urlparse(self.path).query)
                try:
                    eid = int(q.get("id", [""])[0])
                except ValueError:
                    return self._send(400, '{"error":"bad id"}')
                cur = [i for i in eng.db.kv_get("resolved_ids", []) if i != eid]
                if q.get("on", ["1"])[0] == "1":
                    cur.append(eid)
                eng.db.kv_set("resolved_ids", cur[-2000:])   # bounded
                return self._send(200, '{"ok":true}')
            if self.path.startswith("/api/rebaseline"):
                import time as _t
                from . import det_host
                if parse_qs(urlparse(self.path).query).get("clear", ["0"])[0] == "1":
                    eng.db.kv_set("baseline_at", 0)
                    return self._send(200, '{"ok":true}')
                ports, usb = det_host.rebaseline(eng.db)
                # LAN devices seen in the last 10 min become "known". Camera-class devices are deliberately left alone: a camera that is on the
                # network right now may be the very thing being hunted, so it stays flagged until the person decides about it individually.
                now = _t.time()
                rows = eng.db.query("SELECT mac FROM devices WHERE trusted=0 AND last_seen>? AND klass NOT LIKE 'camera%'", (now - 600,))
                for r in rows:
                    eng.db.exec("UPDATE devices SET trusted=1 WHERE mac=?", (r["mac"],))
                left = eng.db.query("SELECT COUNT(*) AS n FROM devices WHERE trusted=0 AND last_seen>? AND klass LIKE 'camera%'", (now - 600,))[0]["n"]
                eng.db.kv_set("baseline_at", now)
                eng.emit("host", "info", "baseline", "x", f"Baseline locked in: {len(rows)} devices, {ports} listening ports, {usb} USB devices", cooldown=0)
                return self._send(200, json.dumps({"ok": True, "devices": len(rows), "ports": ports, "usb": usb, "camera_left": left}))
            if self.path == "/api/beep":
                eng.beep("dashboard")
                eng.emit("host", "info", "beep", "x", "Sensor beep logged", cooldown=0)
                self._send(200, '{"ok":true}')
            else:
                self._send(404, "{}")

    srv = ThreadingHTTPServer((host, port), H)
    threading.Thread(target=srv.serve_forever, daemon=True, name="web").start()
    return srv
