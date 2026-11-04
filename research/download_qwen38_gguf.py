"""Resumable range download of the exact public Ollama language-model blob."""
import concurrent.futures
import hashlib
import json
import os
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path('/Users/josoroma/Models/Qwen3.8-27B-Q4_K_M-Ollama')
PART = ROOT / 'Qwen3.8-27B-Q4_K_M.gguf.part'
FINAL = ROOT / 'Qwen3.8-27B-Q4_K_M.gguf'
STATE = ROOT / 'download-state.json'
DIGEST = 'f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d'
URL = 'https://registry.ollama.ai/v2/library/qwen3.8/blobs/sha256:' + DIGEST
SIZE = 16810714464
CHUNK = 64 * 1024 * 1024
lock = threading.Lock()
inflight = {}
started = time.monotonic()

ROOT.mkdir(parents=True, exist_ok=True)
if FINAL.exists():
    h = hashlib.sha256()
    with FINAL.open('rb') as file:
        while block := file.read(16 * 1024 * 1024):
            h.update(block)
    if FINAL.stat().st_size != SIZE or h.hexdigest() != DIGEST:
        raise RuntimeError('Existing final artifact failed verification; it was not overwritten')
    print(json.dumps({'verified': True, 'reused_existing_file': True,
                      'bytes': SIZE, 'sha256': DIGEST, 'model_path': str(FINAL)}), flush=True)
    raise SystemExit(0)

if STATE.exists():
    if not PART.exists():
        raise RuntimeError('Resume state exists but its partial file is missing; refusing to reuse completion markers')
    state = json.loads(STATE.read_text())
    assert state['digest'] == DIGEST and state['size'] == SIZE
else:
    prefix = PART.stat().st_size if PART.exists() else 0
    assert 0 <= prefix <= SIZE
    state = {'digest': DIGEST, 'size': SIZE, 'prefix_bytes': prefix, 'completed': []}

def save():
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2) + '\n')
    tmp.replace(STATE)

save()
fd = os.open(PART, os.O_RDWR | os.O_CREAT, 0o644)
os.ftruncate(fd, SIZE)
ranges = [(a, min(a + CHUNK, SIZE) - 1) for a in range(state['prefix_bytes'], SIZE, CHUNK)]
completed = set(state['completed'])
initial = state['prefix_bytes'] + sum(b - a + 1 for a, b in ranges if a in completed)

def fetch(pair):
    a, b = pair
    for attempt in range(5):
        try:
            req = urllib.request.Request(URL, headers={'Range': f'bytes={a}-{b}'})
            with urllib.request.urlopen(req, timeout=90) as response:
                expected = f'bytes {a}-{b}/{SIZE}'
                if response.status != 206 or response.headers.get('Content-Range') != expected:
                    raise RuntimeError('Server did not honor exact byte range')
                pos = a
                while data := response.read(1024 * 1024):
                    if pos + len(data) > b + 1:
                        raise RuntimeError('Range exceeded declared end')
                    view = memoryview(data)
                    while view:
                        written = os.pwrite(fd, view, pos)
                        if written <= 0:
                            raise RuntimeError('Failed disk write')
                        pos += written
                        view = view[written:]
                    with lock:
                        inflight[a] = pos - a
                if pos != b + 1:
                    raise RuntimeError('Incomplete range')
            with lock:
                completed.add(a)
                state['completed'] = sorted(completed)
                inflight.pop(a, None)
                save()
            return
        except Exception:
            with lock:
                inflight.pop(a, None)
            if attempt == 4:
                raise
            time.sleep(min(2 ** attempt, 8))

try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch, p) for p in ranges if p[0] not in completed]
        pending = set(futures)
        while pending:
            done, pending = concurrent.futures.wait(pending, timeout=30,
                return_when=concurrent.futures.FIRST_EXCEPTION)
            for future in done:
                future.result()
            with lock:
                received = state['prefix_bytes'] + sum(b-a+1 for a,b in ranges if a in completed) + sum(inflight.values())
            elapsed = time.monotonic() - started
            rate = (received-initial)/max(elapsed, 1)
            print(json.dumps({'downloaded_gb': round(received/1e9,3),
                'total_gb': round(SIZE/1e9,3), 'percent': round(100*received/SIZE,1),
                'mb_per_second': round(rate/1e6,2),
                'remaining_seconds_estimate': round((SIZE-received)/rate) if rate else None}), flush=True)
    os.fsync(fd)
finally:
    os.close(fd)

print('Verifying complete file SHA-256', flush=True)
h = hashlib.sha256()
with PART.open('rb') as file:
    while block := file.read(16*1024*1024):
        h.update(block)
assert PART.stat().st_size == SIZE and h.hexdigest() == DIGEST, 'Artifact verification failed'
PART.replace(FINAL)
verification = {'bytes': SIZE, 'sha256': h.hexdigest(), 'verified': True,
                'model_path': str(FINAL), 'download_seconds_this_session': round(time.monotonic()-started,3)}
(ROOT/'VERIFICATION.json').write_text(json.dumps(verification, indent=2)+'\n')
Path(__file__).with_name('qwen38-gguf-verification.json').write_text(json.dumps(verification,indent=2)+'\n')
print(json.dumps(verification), flush=True)
