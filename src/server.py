#!/usr/bin/env python3
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import json
import os
import signal
import subprocess
import time

from config import (
    ADMIN_TOKEN,
    COOKIE_FILE,
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    DOWNLOAD_DIR,
    DOWNLOAD_LOG,
    DOWNLOAD_NOHUP,
    DOWNLOAD_PID,
    DOWNLOAD_STATE,
    MANIFEST,
    PYTHON_BIN,
    SCAN_LOG,
    SCAN_MANIFEST,
    SCAN_NOHUP,
    SCAN_PID,
    SCAN_STATE,
    SRC_DIR,
    ensure_runtime_dirs,
    is_excluded,
    strip_remote_root,
)

STARTED = time.time()
SPEED_STATE = {"t": 0.0, "bytes": 0, "speed": 0.0}
COOKIE_CACHE = {"t": 0.0, "mtime": None, "data": None}
COOKIE_CHECK_TTL = 60

INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>115 Sync Console</title>
<style>
:root{color-scheme:dark;--bg:#081016;--panel:#0d161e;--line:#243342;--text:#edf6fb;--muted:#91a6b5;--cyan:#4cc9f0;--green:#61e294;--red:#ff6b7a;--amber:#f7c66a}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20% 0%,#153543,transparent 30%),var(--bg);color:var(--text);font:14px/1.45 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.shell{width:min(1420px,100%);margin:auto;padding:22px}header{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:18px}h1{margin:0;font-size:25px}.eyebrow{color:var(--muted);font-size:12px;letter-spacing:.08em;text-transform:uppercase}.pill{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:999px;padding:7px 12px;background:#081018}.dot{width:9px;height:9px;border-radius:50%;background:var(--green);box-shadow:0 0 16px var(--green)}.grid{display:grid;grid-template-columns:1.25fr repeat(3,.55fr);gap:14px}.card{border:1px solid var(--line);border-radius:8px;background:rgba(13,22,30,.9);padding:16px;box-shadow:0 18px 70px rgba(0,0,0,.28)}.hero{min-height:230px}.title{color:var(--muted);font-weight:700;margin-bottom:12px}.speed{font-size:48px;font-weight:800}.sub{color:var(--muted);word-break:break-word}.big{font-size:31px;font-weight:800}.barbox{height:10px;border:1px solid var(--line);background:#071018;border-radius:999px;overflow:hidden;margin-top:22px}.bar{height:100%;width:0;background:linear-gradient(90deg,var(--cyan),var(--green))}.layout{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(360px,.65fr);gap:14px;margin-top:14px}.panel-title{display:flex;justify-content:space-between;align-items:center}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:11px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-size:12px}.path{word-break:break-all}.badge{border-radius:999px;padding:3px 8px;background:#1f3131;color:var(--green);white-space:nowrap}.badge.warn{background:#30291a;color:var(--amber)}.logs{white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;color:#c8d3dc;background:#061018;border:1px solid var(--line);border-radius:8px;padding:12px;max-height:360px;overflow:auto}button,input,textarea{border-radius:8px;border:1px solid var(--line);background:#071018;color:var(--text)}button{min-height:36px;padding:0 12px;cursor:pointer;font-weight:760}button.primary{border-color:#367991;background:#123040}button.green{border-color:#3a7e55;background:#123120}button:disabled{opacity:.55}input{min-height:36px;padding:0 10px}textarea{width:100%;min-height:76px;padding:10px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}.actions{display:flex;flex-wrap:wrap;gap:10px}.statgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.stat{border:1px solid var(--line);border-radius:8px;padding:10px;background:#071018}.ok{color:var(--green)}.warn{color:var(--amber)}.err{color:var(--red)}@media(max-width:1000px){.grid,.layout{grid-template-columns:1fr}.speed{font-size:38px}}
</style>
</head>
<body>
<main class="shell">
<header><div><div class="eyebrow">115 Sync Console</div><h1>下载与扫描监控</h1></div><div><span class="pill"><span class="dot" id="dot"></span><span id="updated">连接中</span></span> <span class="pill" id="uptime">运行 -</span></div></header>
<section class="grid">
<div class="card hero"><div class="title">当前传输速度</div><div class="speed"><span id="speedText">-</span><small>/s</small></div><p class="sub" id="speedSub">等待状态接口</p><div class="statgrid"><div class="stat"><b id="diskText">-</b><div class="sub">当前落盘</div></div><div class="stat"><b id="doneBytesText">-</b><div class="sub">状态记录完成</div></div><div class="stat"><b id="failureText">-</b><div class="sub">失败任务</div></div></div></div>
<div class="card"><div class="title">扫描进度</div><div class="big" id="scanText">-</div><p class="sub" id="scanSub">-</p><div class="barbox"><div class="bar" id="scanBar"></div></div></div>
<div class="card"><div class="title">文件清单</div><div class="big" id="manifestText">-</div><p class="sub" id="manifestSub">-</p><div class="barbox"><div class="bar" id="manifestBar"></div></div></div>
<div class="card"><div class="title">下载进度</div><div class="big" id="downloadText">-</div><p class="sub" id="downloadSub">-</p><div class="barbox"><div class="bar" id="downloadBar"></div></div></div>
</section>
<section class="layout"><div class="card"><div class="panel-title"><h2>正在下载 / 最近文件</h2><span class="sub" id="fileCount">-</span></div><table><thead><tr><th>文件</th><th>大小</th><th>状态</th></tr></thead><tbody id="files"></tbody></table></div>
<aside><div class="card"><h2>扫描与差异同步</h2><div class="actions"><button class="primary" id="scanSyncBtn">扫描并差异同步</button><button class="green" id="syncOnlyBtn">只差异同步</button><input id="adminToken" type="password" placeholder="管理令牌" /></div><div class="statgrid" style="margin-top:10px"><div class="stat"><b id="remoteOnlyText">-</b><div class="sub">待补下载</div></div><div class="stat"><b id="localOkText">-</b><div class="sub">本地已匹配</div></div><div class="stat"><b id="mismatchText">-</b><div class="sub">大小不一致</div></div></div><p class="sub" id="syncMsg">网盘多、本地没有的文件会自动加入下载。</p></div>
<div class="card" style="margin-top:14px"><h2>115 登录态</h2><p id="cookieText">检测中</p><p class="sub" id="cookieSub"></p><form id="cookieForm"><textarea id="cookieInput" placeholder="UID=...; CID=...; SEID=...; KID=..."></textarea><div class="actions"><button class="primary" id="cookieSave">保存并重启下载器</button><span class="sub" id="cookieMsg"></span></div></form></div>
<div class="card" style="margin-top:14px"><h2>任务状态</h2><table><tbody id="tasks"></tbody></table></div><div class="card" style="margin-top:14px"><h2>最近日志</h2><div class="logs" id="logs">加载中...</div></div></aside></section>
</main>
<script>
function fmtBytes(n){if(!Number.isFinite(n)||n<0)return'-';const u=['B','KB','MB','GB','TB'];let i=0;while(n>=1024&&i<u.length-1){n/=1024;i++}return`${n.toFixed(n>=100?0:n>=10?1:2)} ${u[i]}`}
function pct(a,b){return b>0?Math.max(0,Math.min(100,a/b*100)):0}
function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function row(k,v){return`<tr><th>${k}</th><td>${v}</td></tr>`}
function headers(){const t=document.getElementById('adminToken').value.trim()||localStorage.getItem('syncAdminToken')||'';return t?{'Content-Type':'application/json','X-Admin-Token':t}:{'Content-Type':'application/json'}}
function updateDiff(s){const d=s.diff||{};remoteOnlyText.textContent=d.remote_only??'-';localOkText.textContent=d.local_ok??'-';mismatchText.textContent=d.size_mismatch??'-'}
function updateCookie(c){const state=c?.state||'missing';cookieText.innerHTML=state==='ok'?'<span class="ok">正常</span>':state==='expired'?'<span class="err">已过期</span>':'<span class="warn">未设置/异常</span>';cookieSub.textContent=`${c?.message||''} 检测 ${c?.checked_at?new Date(c.checked_at*1000).toLocaleTimeString():'-'}`}
async function tick(){try{const r=await fetch('/api/status',{cache:'no-store'});const s=await r.json();updated.textContent='更新于 '+new Date(s.now*1000).toLocaleTimeString();uptime.textContent='运行 '+s.uptime;dot.style.background=s.tasks.downloader.running?'var(--green)':'var(--amber)';speedText.textContent=fmtBytes(s.speed.bytes_per_sec);speedSub.textContent=s.current_part?s.current_part.path:'等待下一个文件';diskText.textContent=fmtBytes(s.download.bytes_on_disk);doneBytesText.textContent=fmtBytes(s.download.done_bytes);failureText.textContent=s.download.failures;const scanned=s.scan.scanned,queue=s.scan.queue,total=scanned+queue;scanText.textContent=`${scanned} / ${total||'-'}`;scanSub.textContent=s.scan.done?'扫描完成':`待扫描 ${queue} 个目录`;scanBar.style.width=pct(scanned,total)+'%';manifestText.textContent=s.manifest.count+' 个';manifestSub.textContent='已发现 '+fmtBytes(s.manifest.bytes);manifestBar.style.width=s.scan.done?'100%':pct(s.manifest.count,Math.max(s.manifest.count+queue*8,1))+'%';downloadText.textContent=`${s.download.done_count} / ${s.manifest.count}`;downloadSub.textContent=`完成率 ${pct(s.download.done_count,s.manifest.count).toFixed(1)}%`;downloadBar.style.width=pct(s.download.done_count,s.manifest.count)+'%';fileCount.textContent=`显示 ${s.recent_files.length} 个`;updateDiff(s);updateCookie(s.cookie);tasks.innerHTML=row('扫描任务',s.tasks.scanner.running?`<span class="ok">运行中</span> PID ${s.tasks.scanner.pid} ${s.tasks.scanner.elapsed}`:'<span class="warn">未运行</span>')+row('下载任务',s.tasks.downloader.running?`<span class="ok">运行中</span> PID ${s.tasks.downloader.pid} ${s.tasks.downloader.elapsed}`:'<span class="warn">未运行</span>')+row('失败数',s.download.failures)+row('下载目录',esc(s.paths.download_dir||'-'));files.innerHTML=(s.recent_files.length?s.recent_files:[{path:'暂无文件',size:-1,status:'waiting'}]).map(f=>`<tr><td class="path">${esc(f.path)}</td><td>${fmtBytes(f.size)}</td><td><span class="badge ${f.status==='完成'?'':'warn'}">${esc(f.status)}</span></td></tr>`).join('');logs.textContent=(s.logs||[]).join('\n')}catch(e){updated.textContent='连接失败';dot.style.background='var(--red)'}}
cookieForm.addEventListener('submit',async ev=>{ev.preventDefault();const cookie=cookieInput.value.trim();if(!cookie){cookieMsg.textContent='先粘贴 cookie';return}cookieSave.disabled=true;cookieMsg.textContent='保存中...';try{const r=await fetch('/api/cookie',{method:'POST',headers:headers(),body:JSON.stringify({cookie})});const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'保存失败');cookieInput.value='';cookieMsg.textContent='已保存';setTimeout(tick,600)}catch(e){cookieMsg.textContent=e.message}finally{cookieSave.disabled=false}});
async function triggerSync(rescan){const btn=rescan?scanSyncBtn:syncOnlyBtn;btn.disabled=true;syncMsg.textContent=rescan?'正在启动扫描...':'正在重启差异下载...';const token=adminToken.value.trim();if(token)localStorage.setItem('syncAdminToken',token);try{const r=await fetch('/api/sync',{method:'POST',headers:headers(),body:JSON.stringify({rescan})});const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'启动失败');syncMsg.textContent=d.message||'已启动';setTimeout(tick,800)}catch(e){syncMsg.textContent=e.message}finally{btn.disabled=false}}
scanSyncBtn.onclick=()=>triggerSync(true);syncOnlyBtn.onclick=()=>triggerSync(false);adminToken.value=localStorage.getItem('syncAdminToken')||'';tick();setInterval(tick,2000);
</script>
</body>
</html>"""


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def tail_lines(path: Path, n: int = 80) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except Exception:
        return []


def format_duration(seconds: float) -> str:
    sec = int(seconds)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def pid_status(pid_file: Path) -> dict:
    try:
        pid = int(pid_file.read_text().strip())
    except Exception:
        return {"pid": None, "running": False, "elapsed": "-"}
    if not Path(f"/proc/{pid}").exists():
        return {"pid": pid, "running": False, "elapsed": "-"}
    try:
        ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        stat = Path(f"/proc/{pid}/stat").read_text().split()
        start_ticks = int(stat[21])
        uptime = float(Path("/proc/uptime").read_text().split()[0])
        return {"pid": pid, "running": True, "elapsed": format_duration(max(0, uptime - start_ticks / ticks))}
    except Exception:
        return {"pid": pid, "running": True, "elapsed": "-"}


def validate_cookie_text(cookie: str) -> tuple[bool, str]:
    if not cookie.strip():
        return False, "cookie is empty"
    parts = {}
    for item in cookie.split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip().upper()] = value.strip()
    missing = [key for key in ("UID", "SEID") if not parts.get(key)]
    return (False, "missing " + "/".join(missing)) if missing else (True, "")


def cookie_status(force: bool = False) -> dict:
    now = time.time()
    try:
        st = COOKIE_FILE.stat()
    except FileNotFoundError:
        return {"state": "missing", "message": "cookie file not found", "checked_at": now, "updated_at": None}
    cached = COOKIE_CACHE.get("data")
    if not force and cached and COOKIE_CACHE.get("mtime") == st.st_mtime and now - COOKIE_CACHE.get("t", 0) < COOKIE_CHECK_TTL:
        return cached
    try:
        ok, message = validate_cookie_text(COOKIE_FILE.read_text(encoding="utf-8"))
        if not ok:
            data = {"state": "missing", "message": message, "checked_at": now, "updated_at": st.st_mtime}
        else:
            from p115client import P115Client
            info = P115Client(COOKIE_FILE.read_text(encoding="utf-8").strip()).login_info()
            data = {"state": "ok", "message": "login ok" if info.get("state") else "login invalid", "checked_at": now, "updated_at": st.st_mtime}
            if not info.get("state"):
                data["state"] = "expired"
    except Exception as exc:
        data = {"state": "expired", "message": str(exc)[:180], "checked_at": now, "updated_at": st.st_mtime}
    COOKIE_CACHE.update({"t": now, "mtime": st.st_mtime, "data": data})
    return data


def stop_process(pid_file: Path) -> None:
    try:
        pid = int(pid_file.read_text().strip())
    except Exception:
        return
    if not Path(f"/proc/{pid}").exists():
        return
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            if not Path(f"/proc/{pid}").exists():
                return
            time.sleep(0.2)
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def restart_downloader() -> int:
    stop_process(DOWNLOAD_PID)
    state = read_json(DOWNLOAD_STATE, {})
    state["in_progress"] = {}
    tmp = DOWNLOAD_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DOWNLOAD_STATE)
    with DOWNLOAD_NOHUP.open("ab") as out:
        proc = subprocess.Popen([PYTHON_BIN, str(SRC_DIR / "incremental_download.py")], cwd=str(SRC_DIR), stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    DOWNLOAD_PID.write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


def restart_scanner(reset: bool = False) -> int:
    stop_process(SCAN_PID)
    if reset:
        SCAN_STATE.unlink(missing_ok=True)
        SCAN_MANIFEST.unlink(missing_ok=True)
    with SCAN_NOHUP.open("ab") as out:
        proc = subprocess.Popen([PYTHON_BIN, str(SRC_DIR / "scanner.py")], cwd=str(SRC_DIR), stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    SCAN_PID.write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


def manifest_records() -> list[dict]:
    out = []
    seen = set()
    if not MANIFEST.exists():
        return out
    for line in MANIFEST.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        rel = str(rec.get("relpath", ""))
        if is_excluded(rel):
            continue
        key = str(rec.get("fid") or rel)
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def disk_files() -> list[dict]:
    files = []
    if DOWNLOAD_DIR.exists():
        for path in DOWNLOAD_DIR.rglob("*"):
            if path.is_file():
                st = path.stat()
                files.append({"path": str(path.relative_to(DOWNLOAD_DIR)), "size": st.st_size, "mtime": st.st_mtime, "status": "下载中" if path.name.endswith(".part") else "完成"})
    return sorted(files, key=lambda item: item["mtime"], reverse=True)


def diff_summary(recs: list[dict]) -> dict:
    remote_only = local_ok = size_mismatch = missing_bytes = mismatch_bytes = 0
    for rec in recs:
        size = int(rec.get("size") or 0)
        path = DOWNLOAD_DIR / strip_remote_root(str(rec.get("relpath") or ""))
        if not path.exists():
            remote_only += 1
            missing_bytes += size
            continue
        got = path.stat().st_size
        if size == 0 or got == size:
            local_ok += 1
        else:
            size_mismatch += 1
            mismatch_bytes += max(0, size - got)
    return {"remote_only": remote_only, "local_ok": local_ok, "size_mismatch": size_mismatch, "missing_bytes": missing_bytes, "mismatch_bytes": mismatch_bytes}


def status() -> dict:
    now = time.time()
    scan = read_json(SCAN_STATE, {})
    download = read_json(DOWNLOAD_STATE, {"done": {}, "failures": {}})
    recs = manifest_records()
    files = disk_files()
    bytes_on_disk = sum(f["size"] for f in files)
    if SPEED_STATE["t"]:
        dt = max(0.001, now - SPEED_STATE["t"])
        speed = max(0.0, (bytes_on_disk - SPEED_STATE["bytes"]) / dt)
        SPEED_STATE["speed"] = speed * 0.35 + SPEED_STATE["speed"] * 0.65 if SPEED_STATE["speed"] else speed
    SPEED_STATE.update({"t": now, "bytes": bytes_on_disk})
    done = download.get("done") or {}
    failures = download.get("failures") or {}
    rec_keys = {str(r.get("fid") or r.get("relpath")) for r in recs}
    done = {k: v for k, v in done.items() if k in rec_keys}
    failures = {k: v for k, v in failures.items() if k in rec_keys}
    return {
        "now": now,
        "uptime": format_duration(now - STARTED),
        "tasks": {"scanner": pid_status(SCAN_PID), "downloader": pid_status(DOWNLOAD_PID)},
        "scan": {"queue": len(scan.get("queue") or []), "scanned": len(scan.get("scanned") or {}), "done": bool(scan.get("scan_done"))},
        "manifest": {"count": len(recs), "bytes": sum(int(r.get("size") or 0) for r in recs)},
        "diff": diff_summary(recs),
        "download": {"done_count": len(done), "done_bytes": sum(int(v.get("bytes") or 0) for v in done.values() if isinstance(v, dict)), "failures": len(failures), "bytes_on_disk": bytes_on_disk},
        "speed": {"bytes_per_sec": SPEED_STATE["speed"]},
        "cookie": cookie_status(),
        "current_part": next((f for f in files if f["path"].endswith(".part")), None),
        "recent_files": files[:20],
        "tree": {"lines": len(recs)},
        "paths": {"download_dir": str(DOWNLOAD_DIR)},
        "logs": (tail_lines(DOWNLOAD_LOG, 35) + ["--- scanner ---"] + tail_lines(SCAN_LOG, 35))[-80:],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def send_json(self, code: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def require_admin(self) -> bool:
        if not ADMIN_TOKEN or self.headers.get("X-Admin-Token") == ADMIN_TOKEN:
            return True
        self.send_json(401, {"ok": False, "error": "admin token required"})
        return False

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/status":
            self.send_json(200, status())
            return
        if path == "/api/cookie":
            self.send_json(200, cookie_status(force=True))
            return
        if path in {"/", "/index.html"}:
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):
        if not self.require_admin():
            return
        path = urlparse(self.path).path
        try:
            raw = self.rfile.read(min(int(self.headers.get("Content-Length") or "0"), 20000))
            data = json.loads(raw.decode("utf-8") or "{}")
            if path == "/api/cookie":
                cookie = str(data.get("cookie") or "").strip()
                ok, message = validate_cookie_text(cookie)
                if not ok:
                    self.send_json(400, {"ok": False, "error": message})
                    return
                COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
                tmp = COOKIE_FILE.with_suffix(".tmp")
                tmp.write_text(cookie + "\n", encoding="utf-8")
                os.chmod(tmp, 0o600)
                tmp.replace(COOKIE_FILE)
                COOKIE_CACHE.update({"t": 0.0, "mtime": None, "data": None})
                checked = cookie_status(force=True)
                if checked.get("state") != "ok":
                    self.send_json(400, {"ok": False, "error": checked.get("message"), "cookie": checked})
                    return
                self.send_json(200, {"ok": True, "restart": True, "pid": restart_downloader(), "cookie": checked})
                return
            if path == "/api/sync":
                rescan = bool(data.get("rescan", True))
                scanner_pid = restart_scanner(reset=rescan) if rescan else None
                downloader_pid = restart_downloader()
                self.send_json(200, {"ok": True, "message": "started", "scanner_pid": scanner_pid, "downloader_pid": downloader_pid, "status": status().get("diff")})
                return
            self.send_error(404)
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)[:240]})


if __name__ == "__main__":
    ensure_runtime_dirs()
    ThreadingHTTPServer((DASHBOARD_HOST, DASHBOARD_PORT), Handler).serve_forever()
