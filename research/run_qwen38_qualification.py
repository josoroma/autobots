"""Run an isolated local test and restore the user-approved paused Bonsai service.

The private restoration bundle is captured separately, outside this repository.
This script never serializes its environment or authentication credentials.
"""
import datetime as dt
import fcntl
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = Path('/Users/josoroma/Models/Qwen3.8-27B-Q4_K_M-Ollama/Qwen3.8-27B-Q4_K_M.gguf')
REPORT = HERE / 'qwen38-gguf-session.json'
MEMORY = HERE / 'qwen38-gguf-memory.jsonl'
BASE = 'http://127.0.0.1:18081'
ALIAS = 'qwen38-local-qualification'
private_path = Path((HERE / '.bonsai-restore-pointer').read_text().strip())
private = json.loads(private_path.read_text())
session = {'started_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'scope': 'Exact Ollama GGUF artifact served by existing llama.cpp; text-only qualification.',
           'events': [], 'guardrails': {'rss_gib': 24, 'swap_growth_gib': 2,
             'critical_pressure_seconds': 5, 'warning_pressure_seconds': 30,
             'startup_timeout_seconds': 300}}
server = None
job = None
restore_needed = False
baseline = None
pressure_since = None
deferred_signals = []

def event(phase, **detail):
    session['events'].append({'time_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                              'phase': phase, **detail})
    REPORT.write_text(json.dumps(session, indent=2)+'\n')
    print(json.dumps({'phase': phase, **detail}), flush=True)

def cleanup_error(phase, error):
    session.setdefault('cleanup_errors', []).append(
        {'phase': phase, 'type': type(error).__name__, 'message': str(error)})
    try:
        print(json.dumps({'phase': phase, 'error_type': type(error).__name__,
                          'message': str(error)}), file=sys.stderr, flush=True)
    except Exception:
        pass

def safe_event(phase, **detail):
    """Cleanup diagnostics must never prevent restoration."""
    try:
        event(phase, **detail)
    except Exception as error:
        cleanup_error('report_write_failed', error)

def identity(pid):
    return subprocess.run(['ps','-p',str(pid),'-o','lstart=','-o','command='],
                          capture_output=True,text=True).stdout.strip()

def listening(port):
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(('127.0.0.1',port)) == 0

def get(path, auth=None, timeout=3):
    req = urllib.request.Request(path, headers={'Authorization':'Bearer '+auth} if auth else {})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as response:
        return json.load(response)

def memory_sample():
    swap = subprocess.check_output(['sysctl','-n','vm.swapusage'],text=True).strip()
    match = re.search(r'used\s*=\s*([0-9.]+)([MG])',swap)
    swap_bytes = int(float(match[1]) * (1024**2 if match[2]=='M' else 1024**3))
    pressure = int(subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True))
    rss = 0
    if server and server.poll() is None:
        value = subprocess.run(['ps','-p',str(server.pid),'-o','rss='],capture_output=True,text=True).stdout.strip()
        rss = int(value)*1024 if value else 0
    row = {'time_utc':dt.datetime.now(dt.timezone.utc).isoformat(), 'server_pid':server.pid if server else None,
           'rss_bytes':rss,'swap_used_bytes':swap_bytes,'pressure_level':pressure}
    with MEMORY.open('a') as file:
        file.write(json.dumps(row)+'\n')
    return row

def guard():
    global pressure_since
    sample = memory_sample()
    if sample['pressure_level'] != 1:
        pressure_since = pressure_since or time.monotonic()
        limit = 5 if sample['pressure_level'] >= 4 else 30
        if time.monotonic()-pressure_since >= limit:
            raise RuntimeError('Stopped test: sustained host memory pressure')
    else:
        pressure_since = None
    if sample['rss_bytes'] >= 24*1024**3:
        raise RuntimeError('Stopped test: server RSS reached 24 GiB guardrail')
    if sample['swap_used_bytes']-baseline['swap_used_bytes'] >= 2*1024**3:
        raise RuntimeError('Stopped test: host swap grew by 2 GiB')
    if server.poll() is not None:
        raise RuntimeError(f'Test server exited with status {server.returncode}')

def terminate(proc):
    if proc is None or proc.poll() is not None:
        return True
    try:
        proc.terminate()
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            return False
    return proc.poll() is not None

def stop_test_process(proc, label):
    try:
        stopped = terminate(proc)
        if not stopped:
            cleanup_error(label, RuntimeError('Process exit could not be confirmed'))
        return stopped
    except Exception as error:
        cleanup_error(label, error)
        return False

def remove_recovery_bundle():
    """Only called after readiness; cleanup failures do not undo restoration."""
    try:
        private_path.unlink()
    except OSError as error:
        cleanup_error('private_recovery_cleanup_failed', error)
        return
    try:
        (HERE/'.bonsai-restore-pointer').unlink(missing_ok=True)
    except OSError as error:
        cleanup_error('recovery_pointer_cleanup_failed', error)
    try:
        private_path.parent.rmdir()
    except OSError as error:
        cleanup_error('recovery_directory_cleanup_failed', error)

def restore():
    # Match Legalizer's lifecycle lock so its own start/stop cannot race this
    # ownership check, launch, process-record replacement, or readiness probe.
    lock_path = Path(private['record_path']).parent/'lifecycle.lock'
    with lock_path.open('a') as lock:
        os.fchmod(lock.fileno(), 0o600)
        lock_deadline = time.monotonic()+300
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= lock_deadline:
                    raise RuntimeError('Bonsai lifecycle lock remained busy; private recovery state retained')
                time.sleep(0.25)
        restore_locked()

def restore_locked():
    record = private['record']
    argv=private['argv']
    key_path=argv[argv.index('--api-key-file')+1]
    key=Path(key_path).read_text().strip()
    expected=argv[argv.index('--model-id')+1] if '--model-id' in argv else record['model']
    proc = None
    if identity(record['pid']) == record['identity']:
        restored_pid = record['pid']
        safe_event('bonsai_original_still_running',pid=restored_pid)
    else:
        if listening(record['port']):
            raise RuntimeError('Cannot restore automatically: original port was occupied by another process')
        with open(private['log'],'ab',buffering=0) as log:
            proc = subprocess.Popen(private['argv'],cwd=private['cwd'],env=private['env'],
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        restored_pid = proc.pid
        safe_event('bonsai_restore_started',pid=proc.pid)
        new_record = dict(record,pid=proc.pid,identity=identity(proc.pid))
        if not new_record['identity']:
            raise RuntimeError('Cannot establish the restored Bonsai process identity')
        record_path = Path(private['record_path'])
        if record_path.is_symlink():
            raise RuntimeError('Refusing to replace a symlinked Bonsai process record')
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=record_path.parent,
                    prefix='.qwen-restore-', suffix='.tmp', delete=False) as file:
                temp = Path(file.name)
                os.fchmod(file.fileno(), 0o600)
                file.write(json.dumps(new_record,indent=2)+'\n')
                file.flush()
                os.fsync(file.fileno())
            temp.replace(record_path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
    deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(f'Bonsai restoration process exited with status {proc.returncode}')
        if proc is None and identity(restored_pid) != record['identity']:
            raise RuntimeError('Original Bonsai process identity changed during readiness verification')
        try:
            result=get(f'http://127.0.0.1:{record["port"]}/v1/models',auth=key)
        except (OSError, ValueError):
            result = None
        if result and expected in [m.get('id') for m in result.get('data',[])]:
            session['bonsai_restored']=True
            safe_event('bonsai_restored_and_identity_verified',pid=restored_pid,port=record['port'])
            remove_recovery_bundle()
            return
        time.sleep(2)
    raise RuntimeError('Bonsai restoration readiness timed out; private recovery state retained')

def interrupted(signum, frame):
    raise KeyboardInterrupt(f'Received signal {signum}')

def defer_interrupt(signum, frame):
    deferred_signals.append(signum)

signal.signal(signal.SIGTERM,interrupted)
signal.signal(signal.SIGINT,interrupted)

try:
    verification=json.loads((HERE/'qwen38-gguf-verification.json').read_text())
    assert verification['verified'] and MODEL.stat().st_size==verification['bytes']
    assert not listening(18081), 'Qualification port already in use'
    original=private['record']
    assert identity(original['pid'])==original['identity'], 'Original service identity changed; no process stopped'
    event('pre_stop',host_memory=memory_sample())
    restore_needed=True
    subprocess.run(['make','-C',private['cwd'],'model-stop'],check=True,capture_output=True,text=True,timeout=30)
    assert not listening(original['port']), 'Original server still listening'
    event('bonsai_temporarily_stopped')
    time.sleep(3)
    baseline=memory_sample()
    session['baseline_after_bonsai_stop']=baseline
    session['vm_stat_before']=subprocess.check_output(['vm_stat'],text=True)
    argv=['/opt/homebrew/bin/llama-server','--model',str(MODEL),'--alias',ALIAS,
        '--host','127.0.0.1','--port','18081','--offline','--device','MTL0',
        '--gpu-layers','all','--fit','off','--ctx-size','8192','--parallel','1',
        '--batch-size','512','--ubatch-size','128','--cache-type-k','f16','--cache-type-v','f16',
        '--cache-ram','0','--no-cache-prompt','--no-context-shift','--jinja',
        '--reasoning','off','--reasoning-budget','0','--chat-template-kwargs','{"enable_thinking":false}',
        '--n-predict','512','--timeout','120','--metrics','--slots','--perf',
        '--no-webui','--no-agent','--no-mmproj','--log-verbosity','3','--log-timestamps','--log-colors','off']
    session['launch_argv']=argv
    session['runtime_version']=subprocess.check_output([argv[0],'--version'],text=True,stderr=subprocess.STDOUT).strip()
    env={k:v for k,v in os.environ.items() if not k.startswith('LLAMA_ARG_')}
    log=open(HERE/'qwen38-gguf-server.log','wb',buffering=0)
    load_started=time.monotonic()
    server=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env)
    event('qwen_loading',pid=server.pid)
    while time.monotonic()-load_started<300:
        guard()
        try:
            if get(BASE+'/health').get('status')=='ok':
                break
        except (OSError,ValueError):
            pass
        time.sleep(2)
    else:
        raise RuntimeError('Qwen load exceeded 300 second startup limit')
    event('qwen_ready',load_wall_seconds=round(time.monotonic()-load_started,3),memory=memory_sample())
    session['server_models']=get(BASE+'/v1/models')
    session['server_props']=get(BASE+'/props')
    for script,budget in [('probe_qwen38_gguf.py',1900),('benchmark_qwen38_gguf.py',950)]:
        output=open(HERE/(script.removesuffix('.py')+'.log'),'wb',buffering=0)
        job=subprocess.Popen([sys.executable,str(HERE/script),'--base-url',BASE,'--model',ALIAS],stdout=output,stderr=subprocess.STDOUT)
        event('suite_started',script=script)
        deadline=time.monotonic()+budget
        while job.poll() is None:
            guard()
            if time.monotonic()>deadline:
                raise RuntimeError('Suite exceeded supervisor deadline')
            time.sleep(2)
        output.close()
        event('suite_finished',script=script,exit_code=job.returncode)
        if job.returncode != 0:
            session.setdefault('suite_failures', []).append(
                {'script': script, 'exit_code': job.returncode})
        job=None
    with urllib.request.urlopen(BASE+'/metrics',timeout=5) as response:
        (HERE/'qwen38-gguf-metrics.txt').write_bytes(response.read())
    if session.get('suite_failures'):
        raise RuntimeError('Qualification completed with failed suite checks; inspect individual result records')
    event('qualification_finished')
except BaseException as error:
    session['error']={'type':type(error).__name__,'message':str(error)}
    event('qualification_interrupted',error_type=type(error).__name__,message=str(error))
finally:
    # A second interrupt must not abandon the already-authorized restoration.
    signal.signal(signal.SIGTERM,defer_interrupt)
    signal.signal(signal.SIGINT,defer_interrupt)
    try:
        stop_test_process(job, 'qualification_job_cleanup_failed')
    finally:
        qwen_stopped = False
        try:
            qwen_stopped = stop_test_process(server, 'qwen_server_cleanup_failed')
        finally:
            # Restoration takes priority over diagnostics, including disk-full
            # report failures and unavailable host-memory commands.
            if server and qwen_stopped:
                safe_event('qwen_test_server_stopped',returncode=server.returncode)
            if restore_needed:
                try:
                    if not qwen_stopped:
                        raise RuntimeError('Qwen exit was not confirmed; Bonsai was not started and private recovery state is retained')
                    restore()
                except BaseException as error:
                    session['restoration_error']={'type':type(error).__name__,'message':str(error)}
                    safe_event('bonsai_restoration_needs_attention',message=str(error))
    try:
        session['vm_stat_after_session']=subprocess.check_output(['vm_stat'],text=True,timeout=10)
    except Exception as error:
        cleanup_error('final_memory_diagnostics_failed', error)
    if deferred_signals:
        session['signals_deferred_during_restoration'] = deferred_signals
    session['finished_at_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    safe_event('session_finished')

raise SystemExit(1 if session.get('error') or session.get('restoration_error') or session.get('cleanup_errors') else 0)
