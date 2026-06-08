#!/usr/bin/env python3
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import fcntl
import json
import os
import time
import uuid

from p115client import P115Client

from config import (
    COOKIE_FILE,
    DOWNLOAD_DIR,
    DOWNLOAD_LOCK,
    DOWNLOAD_LOG,
    DOWNLOAD_STATE,
    FILE_WORKERS,
    INCLUDE_PREFIX,
    MANIFEST,
    PRIORITY_KEYWORDS,
    RANGE_WORKERS,
    ensure_runtime_dirs,
    is_excluded,
    strip_remote_root,
)

CHUNK = 8 * 1024 * 1024
client: P115Client | None = None


def log(message: str) -> None:
    line = time.strftime("%F %T ") + message
    print(line, flush=True)
    with DOWNLOAD_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state() -> dict:
    if DOWNLOAD_STATE.exists():
        return json.loads(DOWNLOAD_STATE.read_text(encoding="utf-8"))
    return {"done": {}, "failures": {}, "in_progress": {}}


def save_state(state: dict) -> None:
    tmp = DOWNLOAD_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DOWNLOAD_STATE)


def update_state(fn):
    DOWNLOAD_LOCK.touch(exist_ok=True)
    with DOWNLOAD_LOCK.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state()
        result = fn(state)
        save_state(state)
        return result


def records() -> list[dict]:
    if not MANIFEST.exists():
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for line in MANIFEST.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        rel = str(rec.get("relpath", ""))
        if INCLUDE_PREFIX and not rel.startswith(INCLUDE_PREFIX):
            continue
        if is_excluded(rel):
            continue
        key = str(rec.get("fid") or rel)
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def target_path(rec: dict) -> Path:
    return DOWNLOAD_DIR / strip_remote_root(str(rec["relpath"]))


def local_file_matches(rec: dict) -> bool:
    path = target_path(rec)
    size = int(rec.get("size") or 0)
    if not path.exists():
        return False
    try:
        return size == 0 or path.stat().st_size == size
    except OSError:
        return False


def priority_rank(rec: dict) -> int:
    rel = str(rec.get("relpath", ""))
    for i, keyword in enumerate(PRIORITY_KEYWORDS):
        if keyword in rel:
            return i
    return len(PRIORITY_KEYWORDS)


def partial_size(rec: dict) -> int:
    part = target_path(rec).with_suffix(target_path(rec).suffix + ".part")
    try:
        return part.stat().st_size
    except OSError:
        return 0


def claim_record(worker: str) -> dict | None:
    def mutate(state: dict):
        now = time.time()
        active = state.setdefault("in_progress", {})
        done = state.setdefault("done", {})
        failures = state.setdefault("failures", {})
        for key, info in list(active.items()):
            if now - float(info.get("t", 0)) > 6 * 3600:
                active.pop(key, None)
        all_records = records()
        valid_keys = {str(r.get("fid") or r.get("relpath")) for r in all_records}
        for key in list(done):
            if key not in valid_keys:
                done.pop(key, None)
        for rec in all_records:
            key = str(rec.get("fid") or rec.get("relpath"))
            if key in done and not local_file_matches(rec):
                done.pop(key, None)
                active.pop(key, None)
                failures.pop(key, None)
                log(f"diff sync queued missing/mismatch file={rec.get('relpath')}")
        ordered = sorted(all_records, key=lambda r: (priority_rank(r), -partial_size(r), str(r.get("relpath", ""))))
        for rec in ordered:
            key = str(rec.get("fid") or rec.get("relpath"))
            if key in done or key in active:
                continue
            active[key] = {"worker": worker, "relpath": rec.get("relpath"), "t": now}
            return rec
        return None
    return update_state(mutate)


def finish_record(worker: str, rec: dict, status: str, nbytes: int) -> None:
    key = str(rec.get("fid") or rec.get("relpath"))
    def mutate(state: dict) -> None:
        active = state.setdefault("in_progress", {})
        if active.get(key, {}).get("worker") == worker:
            active.pop(key, None)
        if status in {"done", "skip"}:
            state.setdefault("done", {})[key] = {"relpath": rec.get("relpath"), "bytes": nbytes, "t": time.time()}
            state.setdefault("failures", {}).pop(key, None)
        else:
            failures = state.setdefault("failures", {})
            failures[key] = int(failures.get(key, 0)) + 1
    update_state(mutate)


def download_one(rec: dict) -> tuple[str, int, str]:
    assert client is not None
    path = target_path(rec)
    size = int(rec.get("size") or 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    if local_file_matches(rec):
        return "skip", path.stat().st_size, str(path)
    part = path.with_name(path.name + ".part")
    pos = part.stat().st_size if part.exists() else 0
    if size and pos > size:
        part.rename(part.with_name(part.name + f".oversize-{int(time.time())}"))
        pos = 0
    for attempt in range(1, 8):
        try:
            url = client.download_url(rec["pickcode"], strict=False)
            headers = dict(getattr(url, "headers", {}) or {})
            headers.setdefault("User-Agent", "")
            if pos:
                headers["Range"] = f"bytes={pos}-"
            with urlopen(Request(str(url), headers=headers), timeout=120) as resp, part.open("ab" if pos else "wb") as out:
                while True:
                    buf = resp.read(CHUNK)
                    if not buf:
                        break
                    out.write(buf)
            got = part.stat().st_size
            if size == 0 or got == size:
                part.replace(path)
                return "done", got, str(path)
            pos = got
            log(f"partial retry file={rec.get('relpath')} got={got} expected={size}")
        except Exception as exc:
            log(f"error attempt={attempt} file={rec.get('relpath')}: {type(exc).__name__}: {exc}")
            if isinstance(exc, HTTPError) and exc.code == 403 and part.exists():
                part.rename(part.with_name(part.name + f".403-{int(time.time())}"))
                pos = 0
            else:
                pos = part.stat().st_size if part.exists() else 0
            time.sleep(min(180, attempt * 15))
    return "fail", part.stat().st_size if part.exists() else 0, str(part)


def worker_loop(worker: str) -> None:
    while True:
        rec = claim_record(worker)
        if not rec:
            state = load_state()
            log(f"worker={worker} waiting; total={len(records())} done={len(state.get('done', {}))}")
            time.sleep(60)
            continue
        status, nbytes, path = download_one(rec)
        log(f"{status}: worker={worker} bytes={nbytes} {rec.get('relpath')} -> {path}")
        finish_record(worker, rec, status, nbytes)


def main() -> None:
    global client
    ensure_runtime_dirs()
    if not COOKIE_FILE.exists():
        raise SystemExit(f"cookie file not found: {COOKIE_FILE}")
    client = P115Client(COOKIE_FILE.read_text(encoding="utf-8").strip())
    run_id = str(uuid.uuid4())[:8]
    log(f"incremental downloader started run={run_id} file_workers={FILE_WORKERS} range_workers={RANGE_WORKERS}")
    update_state(lambda state: state.__setitem__("in_progress", {}))
    with ThreadPoolExecutor(max_workers=FILE_WORKERS) as executor:
        futures = [executor.submit(worker_loop, f"{run_id}-{i}") for i in range(FILE_WORKERS)]
        for future in as_completed(futures):
            future.result()


if __name__ == "__main__":
    main()
