#!/usr/bin/env python3
from __future__ import annotations

import json
import time

from p115client import P115Client

from config import (
    COOKIE_FILE,
    LIST_PAGE_SIZE,
    MANIFEST,
    ROOT_CID,
    ROOT_NAME,
    SCAN_DIR_DELAY,
    SCAN_LOG,
    SCAN_MANIFEST,
    SCAN_PAGE_DELAY,
    SCAN_STATE,
    ensure_runtime_dirs,
    is_excluded,
)

HEADERS={
    'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) 115Browser/125.0.6422.61 Chrome/125.0.6422.61 Safari/537.36',
    'Referer':'https://115.com/storage/?cid=0&mode=wangpan',
    'Accept':'application/json, text/plain, */*',
}

def log(msg):
    line=time.strftime('%F %T ')+msg
    print(line, flush=True)
    with SCAN_LOG.open('a',encoding='utf-8') as f:
        f.write(line+'\n')

def load_state():
    if SCAN_STATE.exists():
        return json.loads(SCAN_STATE.read_text())
    SCAN_MANIFEST.unlink(missing_ok=True)
    return {'queue':[[ROOT_CID,ROOT_NAME]],'scanned':{},'scan_done':False}

def save_state(st):
    tmp=SCAN_STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(st,ensure_ascii=False,indent=2))
    tmp.replace(SCAN_STATE)

def safe(name): return (name or '').replace('/','_').replace('\x00','')

def append_manifest(rec):
    with SCAN_MANIFEST.open('a',encoding='utf-8') as f:
        f.write(json.dumps(rec,ensure_ascii=False)+'\n')

def list_dir(client, cid, limit=LIST_PAGE_SIZE):
    out=[]; off=0
    while True:
        payload={'cid':str(cid),'limit':limit,'offset':off,'show_dir':1}
        r=client.fs_files_aps(payload, headers=HEADERS)
        if r.get('state') is False:
            raise RuntimeError(r)
        data=r.get('data') or []
        out.extend(data)
        count=int(r.get('count') or len(out))
        if off+len(data)>=count or not data: return out
        off += len(data)
        time.sleep(SCAN_PAGE_DELAY)

def scan_step(client, st):
    if not st['queue']:
        st['scan_done']=True
        save_state(st)
        SCAN_MANIFEST.replace(MANIFEST)
        log('scan complete; manifest promoted')
        return
    cid, rel = st['queue'].pop(0)
    if cid in st['scanned']:
        save_state(st); return
    try:
        items=list_dir(client, cid)
    except Exception as e:
        st['queue'].insert(0,[cid,rel]); save_state(st)
        msg=str(e)
        wait=600 if '405' in msg or 'HTTPStatusError' in type(e).__name__ else 180
        log(f'scan blocked/error cid={cid} rel={rel} wait={wait}s {type(e).__name__}: {msg[:240]}')
        time.sleep(wait)
        return
    files=dirs=0
    for it in items:
        name=safe(it.get('n') or it.get('fn') or '')
        if not name: continue
        child_rel=rel+'/'+name
        if is_excluded(child_rel):
            log(f'excluded rel={child_rel}')
            continue
        if 'fid' in it:
            rec={'fid':str(it['fid']),'cid':str(it.get('cid','')),'pickcode':it['pc'],'relpath':child_rel,'size':int(it.get('s') or 0),'sha1':it.get('sha') or ''}
            append_manifest(rec); files += 1
        elif 'cid' in it:
            st['queue'].append([str(it['cid']), child_rel]); dirs += 1
    st['scanned'][cid]={'rel':rel,'items':len(items),'files':files,'dirs':dirs,'t':time.time()}
    save_state(st)
    manifest_lines=sum(1 for _ in SCAN_MANIFEST.open()) if SCAN_MANIFEST.exists() else 0
    log(f'scanned rel={rel} items={len(items)} files={files} dirs={dirs} queue={len(st["queue"])} manifest_lines={manifest_lines}')
    time.sleep(SCAN_DIR_DELAY)

def main():
    ensure_runtime_dirs()
    if not ROOT_CID:
        raise SystemExit('SYNC_ROOT_CID is required')
    if not COOKIE_FILE.exists():
        raise SystemExit(f'cookie file not found: {COOKIE_FILE}')
    client=P115Client(COOKIE_FILE.read_text(encoding='utf-8').strip())
    log('scanner started')
    while True:
        st=load_state()
        if st.get('scan_done'):
            return
        scan_step(client, st)

if __name__=='__main__':
    main()
