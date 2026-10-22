"""Desktop RF spectrum viewer (RTL-SDR): live spectrum + waterfall in the browser, plus a one-shot
24 MHz-1.7 GHz overview map. Needs numpy and rtl_sdr/rtl_power (apt install rtl-sdr).

It shows signal strength by frequency. It cannot decode content, and it cannot tell you what a
signal IS: the band labels are the usual allocations, not an identification.
"""
import json
import math
import queue
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RATE = 2_400_000                 # S/s = visible bandwidth
NFFT = 2048
NFRAME = 50                      # FFTs per frame; 50*2048 samples divides by 10, 5 and 50 so decimation stays aligned
AUDIO = 48_000
POINTS = 1024                    # bins sent to the browser per frame
LO, HI = 24e6, 1766e6            # R820T tuning range

# (low MHz, high MHz, label) - usual allocations in the US, for orientation only
BANDS = [
    (87.8, 108.0, "FM radio"), (108.0, 118.0, "Aviation nav"), (118.0, 137.0, "Aircraft voice"),
    (144.0, 148.0, "Ham 2 m"), (150.0, 162.0, "Public safety / business"),
    (156.0, 162.0, "Marine VHF"), (162.4, 162.55, "NOAA weather"), (174.0, 216.0, "VHF TV"),
    (222.0, 225.0, "Ham 1.25 m"), (314.0, 316.0, "315 MHz remotes"), (420.0, 450.0, "Ham 70 cm"),
    (433.05, 434.79, "433 MHz remotes/sensors"), (462.5, 467.7, "FRS / GMRS walkie-talkies"),
    (470.0, 698.0, "UHF TV"), (698.0, 806.0, "LTE 700"), (824.0, 849.0, "Cell uplink"),
    (869.0, 894.0, "Cell 850 downlink"), (902.0, 928.0, "ISM 915 (meters, remotes)"),
    (929.0, 932.0, "Pagers"), (1090.0, 1090.0, "ADS-B aircraft"),
    (1575.4, 1575.4, "GPS L1"),
]


def have_tools():
    return bool(shutil.which("rtl_sdr") and shutil.which("rtl_power"))


def label_for(mhz):
    hits = [b for b in BANDS if b[0] - 0.05 <= mhz <= b[1] + 0.05]
    return min(hits, key=lambda b: b[1] - b[0])[2] if hits else ""


def _lowpass(cutoff, rate, taps):
    import numpy as np
    n = np.arange(taps) - (taps - 1) / 2
    h = np.sinc(2 * cutoff / rate * n) * np.hamming(taps)
    return (h / h.sum()).astype("float32")


class Decim:
    """FIR low-pass + keep every D-th sample, carrying state between chunks (chunk length must be a multiple of D)."""

    def __init__(self, cutoff, rate, taps, D):
        import numpy as np
        self.np, self.h, self.D = np, _lowpass(cutoff, rate, taps), D
        self.tail = None

    def __call__(self, x):
        np = self.np
        if self.tail is None:
            self.tail = np.zeros(len(self.h) - 1, dtype=x.dtype)
        buf = np.concatenate([self.tail, x])
        self.tail = buf[-(len(self.h) - 1):]
        return np.convolve(buf, self.h, mode="valid")[::self.D]


class Demod:
    """Mixes a channel to baseband, filters, demodulates to 48 kHz mono int16."""

    def __init__(self):
        import numpy as np
        self.np = np
        self.mode = None
        self.ph = 0.0
        self.reset("nfm")

    def reset(self, mode):
        self.mode = mode
        self.last = 1 + 0j
        self.dc = 1.0
        self.de = 0.0
        self.nf = 0.0
        self.s1 = Decim(100e3 if mode == "wbfm" else 15e3, RATE, 33 if mode == "wbfm" else 65, 10)   # -> 240 kHz
        self.s2 = Decim(15e3 if mode == "wbfm" else 6e3, 240e3, 65 if mode == "wbfm" else 129, 5)     # -> 48 kHz
        self.fm_gain = 1 / (2 * math.pi * 75e3 / 240e3)

    def __call__(self, z, off_hz, mode, squelch):
        np = self.np
        if mode != self.mode:
            self.reset(mode)
        n = len(z)
        step = 2 * math.pi * off_hz / RATE
        ph = self.ph + step * np.arange(n)
        self.ph = (self.ph + step * n) % (2 * math.pi)
        x = self.s1(z * np.exp(-1j * ph).astype("complex64"))
        if mode == "wbfm":
            d = np.angle(x * np.conj(np.concatenate([[self.last], x[:-1]])))
            self.last = x[-1]
            out = self.s2(d.astype("float32") * self.fm_gain)
            a = 1 - math.exp(-1 / (AUDIO * 75e-6))               # US 75 us de-emphasis
            y, o = self.de, np.empty_like(out)
            for i, v in enumerate(out):
                y += a * (v - y)
                o[i] = y
            self.de = y
            out = o * 0.8
        else:
            x = self.s2(x)
            pdb = 10 * math.log10(float(np.mean(np.abs(x) ** 2)) + 1e-12)
            self.nf = pdb if self.nf == 0.0 else min(pdb, self.nf + 0.05)   # slow-rising noise-floor tracker
            if mode == "am":
                m = np.abs(x)
                self.dc = 0.98 * self.dc + 0.02 * float(m.mean())
                out = (m / (self.dc + 1e-9) - 1) * 1.5
            else:
                d = np.angle(x * np.conj(np.concatenate([[self.last], x[:-1]])))
                self.last = x[-1]
                out = d / (2 * math.pi * 5e3 / AUDIO) * 0.6
            if squelch and pdb < self.nf + 6:
                out = out * 0
        return (np.clip(out, -1, 1) * 32000).astype("<i2").tobytes()


class Radio:
    """Owns the dongle. One mode at a time: live (rtl_sdr stream) or overview (rtl_power)."""

    def __init__(self):
        import numpy as np
        self.np = np
        self.lock = threading.Lock()
        self.center = 98.5e6
        self.gain = 30.0
        self.frame = None            # latest dB row
        self.seq = 0
        self.error = ""
        self.overview = None
        self.ov_busy = False
        self._want = None            # (center, gain) the capture thread should be running
        self._stop = False
        self.listen = None            # (mode, Hz) while someone is listening
        self.squelch = True
        self.subs = []
        self.demod = Demod()
        self.win = np.hanning(NFFT).astype("float32")
        self.proc = None
        threading.Thread(target=self._run, daemon=True).start()

    def tune(self, center=None, gain=None):
        with self.lock:
            if center is not None:
                if self.listen and abs(self.listen[1] - self.center) < 1:
                    self.listen = (self.listen[0], center)
                self.center = min(max(center, LO + RATE / 2), HI - RATE / 2)
            if gain is not None:
                self.gain = min(max(gain, 0.0), 49.6)
            self._want = (self.center, self.gain)
        if self.proc:
            try:
                self.proc.terminate()
            except OSError:
                pass

    def _run(self):
        np = self.np
        while not self._stop:
            if self.ov_busy:
                time.sleep(0.2)
                continue
            with self.lock:
                c, g = self.center, self.gain
                self._want = None
            cmd = ["rtl_sdr", "-f", str(int(c)), "-s", str(RATE), "-g", str(g), "-"]
            try:
                self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            except OSError as e:
                self.error = str(e)
                time.sleep(2)
                continue
            self.error = ""
            n = NFFT * 2 * NFRAME                  # bytes per frame
            got = False
            while not self._stop and self._want is None and not self.ov_busy:
                buf = self.proc.stdout.read(n)
                if not buf or len(buf) < n:
                    break
                got = True
                x = np.frombuffer(buf, dtype=np.uint8).astype("float32").reshape(-1, 2)
                z = (x[:, 0] - 127.5) + 1j * (x[:, 1] - 127.5)
                if self.listen and self.subs:
                    self._listen(z)
                z = z.reshape(-1, NFFT) * self.win
                p = (np.abs(np.fft.fftshift(np.fft.fft(z, axis=1), axes=1)) ** 2).mean(axis=0)
                db = 10 * np.log10(p + 1e-9)
                db = db.reshape(POINTS, -1).mean(axis=1)
                mid = POINTS // 2                  # hide the RTL DC spike
                db[mid - 1:mid + 2] = (db[mid - 3] + db[mid + 3]) / 2
                self.frame = [round(float(v), 1) for v in db]
                self.seq += 1
            try:
                self.proc.kill()
                self.proc.wait(timeout=2)
            except Exception:
                pass
            if not got and self._want is None and not self.ov_busy:
                self.error = "No data from the dongle. Is it plugged in, and is another program using it?"
                time.sleep(2)

    def _listen(self, z):
        mode, f = self.listen
        off = f - self.center
        if abs(off) > RATE / 2 - 120e3:
            return                                   # outside the visible slice: retune first
        pcm = self.demod(z, off, mode, self.squelch)
        for q in list(self.subs):
            try:
                q.put_nowait(pcm)
            except queue.Full:
                pass

    def run_overview(self):
        if self.ov_busy:
            return
        self.ov_busy = True
        if self.proc:
            try:
                self.proc.kill()
            except OSError:
                pass
        threading.Thread(target=self._overview, daemon=True).start()

    def _overview(self):
        try:
            time.sleep(0.5)
            r = subprocess.run(["rtl_power", "-f", f"{int(LO)}:{int(HI)}:200k", "-i", "2", "-1", "-g", str(self.gain), "-"],
                               capture_output=True, text=True, timeout=180)
            pts = []
            for line in r.stdout.splitlines():
                p = [s.strip() for s in line.split(",")]
                if len(p) < 7:
                    continue
                lo, step = float(p[2]), float(p[4])
                pts += [(lo + i * step, float(v)) for i, v in enumerate(p[6:])]
            pts.sort()
            self.overview = {"t": int(time.time()), "f": [round(a / 1e6, 3) for a, _ in pts],
                             "db": [round(b, 1) for _, b in pts]}
        except Exception as e:
            self.error = f"Overview failed: {e}"
        finally:
            self.ov_busy = False


def serve(host="127.0.0.1", port=8780):
    if not have_tools():
        raise SystemExit("rtl_sdr / rtl_power not found. Install:  sudo apt install rtl-sdr")
    try:
        import numpy  # noqa: F401
    except ImportError:
        raise SystemExit("numpy is needed:  pip install numpy")
    radio = Radio()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype="application/json"):
            b = body.encode() if isinstance(body, str) else body
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            path, _, q = self.path.partition("?")
            args = dict(kv.split("=", 1) for kv in q.split("&") if "=" in kv)
            if path == "/":
                return self._send(PAGE, "text/html; charset=utf-8")
            if path == "/api/tune":
                try:
                    radio.tune(float(args["f"]) * 1e6 if "f" in args else None,
                               float(args["g"]) if "g" in args else None)
                except ValueError:
                    pass
            if path == "/api/listen":
                try:
                    if args.get("mode", "off") == "off":
                        radio.listen = None
                    else:
                        radio.listen = (args["mode"] if args["mode"] in ("wbfm", "nfm", "am") else "nfm",
                                        float(args["f"]) * 1e6)
                    radio.squelch = args.get("sq", "1") != "0"
                except (ValueError, KeyError):
                    pass
            if path == "/api/audio":
                q = queue.Queue(maxsize=40)
                radio.subs.append(q)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    while True:
                        try:
                            self.wfile.write(q.get(timeout=1))
                        except queue.Empty:
                            self.wfile.write(b"")
                            if radio._stop:
                                break
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    radio.subs.remove(q)
                return
            if path in ("/api/frame", "/api/tune", "/api/listen"):
                return self._send(json.dumps({"seq": radio.seq, "center": radio.center / 1e6, "rate": RATE / 1e6,
                                              "gain": radio.gain, "db": radio.frame, "error": radio.error,
                                              "busy": radio.ov_busy, "bands": BANDS,
                                              "listen": radio.listen and [radio.listen[0], radio.listen[1] / 1e6]}))
            if path == "/api/overview":
                return self._send(json.dumps({"busy": radio.ov_busy, "data": radio.overview, "bands": BANDS}))
            if path == "/api/overview/run":
                radio.run_overview()
                return self._send('{"ok":true}')
            self.send_response(404)
            self.end_headers()

    srv = ThreadingHTTPServer((host, port), H)
    print(f"N0RMA spectrum: http://{host}:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>N0RMA Spectrum</title>
<style>
:root{--bg:#0b0f14;--fg:#d6e2ee;--mut:#7d8fa3;--acc:#35d0ba;--card:#121922}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif}
header{display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:10px 14px;background:var(--card);border-bottom:1px solid #1f2b38}
h1{font-size:16px;margin:0 8px 0 0;color:var(--acc)}button,input{background:#1b2633;color:var(--fg);border:1px solid #2a394a;border-radius:6px;padding:6px 10px;font:inherit}
button{cursor:pointer}button:hover,button.on{border-color:var(--acc);color:var(--acc)}
#freq{width:110px}main{padding:10px 14px}canvas{width:100%;display:block;background:#05080c;border-radius:6px;cursor:crosshair}
#spec{height:260px}#fall{height:300px;margin-top:6px}#ov{height:200px;margin-top:6px}
.row{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px;color:var(--mut)}.card{background:var(--card);border-radius:8px;padding:10px 14px;margin-top:10px}
#peaks span{display:inline-block;margin:2px 14px 2px 0;color:var(--fg)}#err{color:#ff7b72}small{color:var(--mut)}
</style></head><body>
<header><h1>N0RMA Spectrum</h1>
<label>Center <input id="freq" value="98.5"> MHz</label><button id="go">Tune</button>
<span id="presets"></span>
<label>Gain <input id="gain" type="range" min="0" max="49.6" step="0.1" value="30"> <span id="gv">30</span> dB</label>
<button id="hold">Peak hold</button>
<span id="lis"><select id="mode"><option value="auto">Auto mode</option><option value="wbfm">FM broadcast</option><option value="nfm">Narrow FM (radios)</option><option value="am">AM (aircraft)</option></select> <button id="listen">▶ Listen</button> <label>Vol <input id="vol" type="range" min="0" max="2" step="0.05" value="1" style="width:80px"></label> <label><input type="checkbox" id="sq" checked> Squelch</label></span><button id="ovb">Scan 24 MHz–1.7 GHz</button><span id="err"></span></header>
<main>
<canvas id="spec" width="1400" height="260"></canvas>
<canvas id="fall" width="1400" height="300"></canvas>
<div class="row"><span id="cur">Hover the graph…</span><span>Click anywhere to tune there. Bright = stronger signal.</span></div>
<div class="card"><b>Strongest signals right now</b> <small>(labels are the usual allocation for that frequency, not an identification)</small><div id="peaks"></div></div>
<div class="card"><b>Whole-spectrum overview</b> <small id="ovs">Press “Scan” – takes about a minute and pauses the live view.</small>
<canvas id="ov" width="1400" height="200"></canvas></div>
</main>
<script>
const $=id=>document.getElementById(id);
const PRE=[["FM radio",98.5],["Airband",125],["NOAA",162.475],["433 MHz",433.9],["GMRS",462.6],["Cell 850",881],["ISM 915",915],["ADS-B",1090]];
PRE.forEach(([n,f])=>{const b=document.createElement('button');b.textContent=n;b.onclick=()=>{tune(f);if(listening)setListen(f)};$('presets').appendChild(b)});
let listening=null,actx=null,gainNode=null,nextT=0,abortAudio=null;
function autoMode(f){return f>=87.8&&f<=108?'wbfm':(f>=108&&f<137?'am':'nfm')}
function curMode(f){const m=$('mode').value;return m==='auto'?autoMode(f):m}
function setListen(f){listening=f;fetch('/api/listen?mode='+curMode(f)+'&f='+f+'&sq='+($('sq').checked?1:0));
 $('listen').textContent='■ Stop';$('listen').classList.add('on')}
async function startAudio(){actx=actx||new AudioContext({sampleRate:48000});await actx.resume();
 gainNode=gainNode||actx.createGain();gainNode.connect(actx.destination);gainNode.gain.value=parseFloat($('vol').value);
 abortAudio=new AbortController();nextT=0;let odd=null;
 const r=(await fetch('/api/audio',{signal:abortAudio.signal})).body.getReader();
 (async()=>{try{for(;;){const {value,done}=await r.read();if(done)break;let b=value;
  if(odd){const t=new Uint8Array(b.length+1);t[0]=odd[0];t.set(b,1);b=t;odd=null}
  if(b.length%2){odd=[b[b.length-1]];b=b.subarray(0,b.length-1)}
  const i16=new Int16Array(b.buffer.slice(b.byteOffset,b.byteOffset+b.length)),f32=new Float32Array(i16.length);
  for(let i=0;i<i16.length;i++)f32[i]=i16[i]/32768;
  const buf=actx.createBuffer(1,f32.length,48000);buf.copyToChannel(f32,0);
  const now=actx.currentTime;if(nextT<now+0.12)nextT=now+0.12;if(nextT>now+0.8){continue}
  const s=actx.createBufferSource();s.buffer=buf;s.connect(gainNode);s.start(nextT);nextT+=buf.duration}}catch(e){}})()}
function stopListen(){listening=null;fetch('/api/listen?mode=off');if(abortAudio)abortAudio.abort();$('listen').textContent='▶ Listen';$('listen').classList.remove('on')}
$('listen').onclick=async()=>{if(listening){stopListen();return}const f=window._d?window._d.center:parseFloat($('freq').value);await startAudio();setListen(f)};
$('vol').oninput=e=>{if(gainNode)gainNode.gain.value=parseFloat(e.target.value)};
$('mode').onchange=()=>{if(listening)setListen(listening)};$('sq').onchange=()=>{if(listening)setListen(listening)};
let st=null,bands=[],hold=false,peak=null,floorDb=-5,topDb=40,seq=-1;
const spec=$('spec'),sx=spec.getContext('2d'),fall=$('fall'),fx=fall.getContext('2d'),ov=$('ov'),ox=ov.getContext('2d');
function tune(f,g){let u='/api/tune?';if(f!=null)u+='f='+f+'&';if(g!=null)u+='g='+g;peak=null;fetch(u)}
$('go').onclick=()=>{const f=parseFloat($('freq').value);tune(f);if(listening)setListen(f)};
$('freq').onkeydown=e=>{if(e.key==='Enter')$('go').click()};
$('gain').oninput=e=>{$('gv').textContent=e.target.value};$('gain').onchange=e=>tune(null,parseFloat(e.target.value));
$('hold').onclick=e=>{hold=!hold;e.target.classList.toggle('on',hold);peak=null};
$('ovb').onclick=()=>{fetch('/api/overview/run');pollOv()};
function color(v){let t=Math.max(0,Math.min(1,(v-floorDb)/(topDb-floorDb)));
 const s=[[0,0,40],[30,0,130],[0,150,200],[240,220,60],[255,255,255]];let p=t*(s.length-1),i=Math.min(s.length-2,Math.floor(p)),k=p-i;
 return 'rgb('+s[i].map((a,j)=>Math.round(a+(s[i+1][j]-a)*k)).join(',')+')'}
function fx2(i,n,c,r){return c-r/2+(i/(n-1))*r}
function draw(d){const n=d.db.length,W=spec.width,H=spec.height;
 const sorted=[...d.db].sort((a,b)=>a-b),med=sorted[n>>1];floorDb=med-10;topDb=Math.max(sorted[n-1]+3,med+25);
 sx.fillStyle='#05080c';sx.fillRect(0,0,W,H);
 const lo=d.center-d.rate/2,hi=d.center+d.rate/2;
 // band shading + labels
 sx.font='11px system-ui';bands.forEach(b=>{if(b[1]<lo||b[0]>hi)return;const x0=(Math.max(b[0],lo)-lo)/d.rate*W,x1=(Math.min(b[1],hi)-lo)/d.rate*W;
  sx.fillStyle='rgba(53,208,186,.10)';sx.fillRect(x0,0,Math.max(2,x1-x0),H);sx.fillStyle='#35d0ba';sx.fillText(b[2],x0+3,12)});
 if(d.listen){const x=(d.listen[1]-lo)/d.rate*W;sx.strokeStyle='#ffb454';sx.beginPath();sx.moveTo(x,0);sx.lineTo(x,H);sx.stroke();sx.fillStyle='#ffb454';sx.fillText('♪ '+d.listen[1].toFixed(3)+' '+d.listen[0].toUpperCase(),x+4,26)}
 // grid
 sx.strokeStyle='#18222e';sx.fillStyle='#7d8fa3';for(let k=0;k<=8;k++){const x=k/8*W;sx.beginPath();sx.moveTo(x,0);sx.lineTo(x,H);sx.stroke();sx.fillText((lo+k/8*d.rate).toFixed(2),x+2,H-4)}
 const y=v=>H-18-(v-floorDb)/(topDb-floorDb)*(H-34);
 if(hold){if(!peak)peak=[...d.db];peak=peak.map((p,i)=>Math.max(p,d.db[i]));sx.strokeStyle='#ffb454';sx.beginPath();peak.forEach((v,i)=>{const x=i/(n-1)*W;i?sx.lineTo(x,y(v)):sx.moveTo(x,y(v))});sx.stroke()}
 sx.strokeStyle='#35d0ba';sx.lineWidth=1.5;sx.beginPath();d.db.forEach((v,i)=>{const x=i/(n-1)*W;i?sx.lineTo(x,y(v)):sx.moveTo(x,y(v))});sx.stroke();sx.lineWidth=1;
 // waterfall
 fx.drawImage(fall,0,0,W,fall.height-1,0,1,W,fall.height-1);
 const img=fx.createImageData(W,1);d.db.forEach((v,i)=>{const c=color(v).match(/\d+/g).map(Number);const x0=Math.floor(i/n*W),x1=Math.floor((i+1)/n*W);for(let x=x0;x<Math.max(x1,x0+1);x++){const o=x*4;img.data[o]=c[0];img.data[o+1]=c[1];img.data[o+2]=c[2];img.data[o+3]=255}});
 fx.putImageData(img,0,0);
 // peaks
 const idx=[...d.db.keys()].sort((a,b)=>d.db[b]-d.db[a]),pick=[];
 for(const i of idx){if(pick.length>=6||d.db[i]<med+8)break;if(pick.every(j=>Math.abs(j-i)>12))pick.push(i)}
 $('peaks').innerHTML=pick.length?pick.map(i=>{const f=lo+i/(n-1)*d.rate,b=bands.filter(b=>f>=b[0]-.05&&f<=b[1]+.05).sort((a,b)=>(a[1]-a[0])-(b[1]-b[0]))[0];
  return '<span><b>'+f.toFixed(3)+' MHz</b> '+(d.db[i]-med).toFixed(0)+' dB above noise'+(b?' · '+b[2]:'')+'</span>'}).join(''):'<small>Nothing stands out above the noise here.</small>';
 $('gv').textContent=d.gain.toFixed(1);window._d=d}
function mhzAt(e,c){const r=c.getBoundingClientRect(),d=window._d;return d?d.center-d.rate/2+(e.clientX-r.left)/r.width*d.rate:null}
[spec,fall].forEach(c=>{c.onmousemove=e=>{const f=mhzAt(e,c);if(f)$('cur').textContent=f.toFixed(3)+' MHz';};
 c.onclick=e=>{const f=mhzAt(e,c);if(!f)return;if(listening){setListen(+f.toFixed(3))}else{$('freq').value=f.toFixed(3);tune(f)}}});
async function loop(){try{const d=await (await fetch('/api/frame')).json();bands=d.bands;
  $('err').textContent=d.error||(d.busy?'Overview scan running – live view paused':'');
  if(d.db&&d.seq!==seq){seq=d.seq;draw(d);if(document.activeElement!==$('freq'))$('freq').value=d.center.toFixed(3)}}catch(e){}
 setTimeout(loop,90)}
async function pollOv(){const o=await (await fetch('/api/overview')).json();
 if(o.busy){$('ovs').textContent='Scanning… (about a minute)';return setTimeout(pollOv,2000)}
 if(!o.data)return;const f=o.data.f,db=o.data.db,W=ov.width,H=ov.height;
 const s=[...db].sort((a,b)=>a-b),lo=s[0]-2,hi=s[s.length-1]+2;ox.fillStyle='#05080c';ox.fillRect(0,0,W,H);
 const f0=24,f1=1766,X=v=>(v-f0)/(f1-f0)*W,Y=v=>H-14-(v-lo)/(hi-lo)*(H-26);
 ox.font='11px system-ui';o.bands.forEach(b=>{if(b[1]-b[0]<.5)return;ox.fillStyle='rgba(53,208,186,.12)';ox.fillRect(X(b[0]),0,Math.max(2,X(b[1])-X(b[0])),H)});
 ox.strokeStyle='#35d0ba';ox.beginPath();f.forEach((v,i)=>{i?ox.lineTo(X(v),Y(db[i])):ox.moveTo(X(v),Y(db[i]))});ox.stroke();
 ox.fillStyle='#7d8fa3';for(let m=100;m<=1700;m+=200)ox.fillText(m+' MHz',X(m)+2,H-2);
 $('ovs').textContent='Click the map to jump the live view there. Scanned '+new Date(o.data.t*1000).toLocaleTimeString()+'.';
 ov.onclick=e=>{const r=ov.getBoundingClientRect(),m=f0+(e.clientX-r.left)/r.width*(f1-f0);$('freq').value=m.toFixed(3);tune(m);scrollTo(0,0)}}
loop();pollOv();
</script></body></html>"""
