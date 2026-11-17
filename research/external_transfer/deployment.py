"""NATS Core deployment on Linux. Usage: python3 deployment.py PLAN.jsonl NEW_OUTPUT.jsonl"""
import collections
import contextlib
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
import socket
import struct
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pubsub_transfer"))
from field_sink import sham_field, write_field


NOW = time.monotonic_ns
ORDER = struct.Struct(">I")
STATE = struct.Struct("<Bd")
DEFAULT_BIN = Path(__file__).resolve().parents[2] / "build/external-transfer/nats-server-v2.11.9-linux-amd64/nats-server"


def wait(deadline):
    while True:
        gap = deadline - NOW()
        if gap <= 0:
            return
        time.sleep((gap-200000)/1e9 if gap > 400000 else 0)


class Client:
    """Small NATS/1.0 text protocol client. Every connection has one active owner."""
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=6)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.reader = self.sock.makefile("rb")
        line = self.reader.readline()
        if not line.startswith(b"INFO "):
            self.close()
            raise ValueError("broker greeting is not NATS INFO")
        self.info = json.loads(line[5:])
        self.sock.sendall(b'CONNECT {"verbose":false,"pedantic":true,"lang":"python","version":"1"}\r\n')

    def close(self):
        self.reader.close()
        self.sock.close()

    def flush(self):
        self.sock.sendall(b"PING\r\n")
        if self.reader.readline() != b"PONG\r\n":
            raise RuntimeError("broker did not acknowledge flush")

    def publish(self, subject, body):
        self.sock.sendall(b"PUB "+subject+b" "+str(len(body)).encode()+b"\r\n"+body+b"\r\n")

    def sub(self, subject):
        self.sock.sendall(b"SUB "+subject+b" 1\r\n")
        self.flush()

    def message(self):
        while True:
            line = self.reader.readline()
            if line == b"PING\r\n":
                self.sock.sendall(b"PONG\r\n")
                continue
            parts = line.split()
            if len(parts) != 4 or parts[0] != b"MSG" or parts[2] != b"1":
                raise RuntimeError("bad NATS message: "+repr(line[:100]))
            size = int(parts[3])
            body = self.reader.read(size)
            if len(body) != size or self.reader.read(2) != b"\r\n":
                raise RuntimeError("incomplete broker message")
            return parts[1], body


@contextlib.contextmanager
def broker(binary):
    with socket.socket() as slot:
        slot.bind(("127.0.0.1", 0))
        port = slot.getsockname()[1]
    name = "research-"+str(os.getpid())+"-"+str(NOW())
    proc = subprocess.Popen([str(binary), "-a", "127.0.0.1", "-p", str(port), "-n", name],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            if proc.poll() is not None:
                raise RuntimeError("NATS server exited during startup")
            try:
                with contextlib.closing(Client(port)) as probe:
                    probe.flush()
                    info = probe.info
                break
            except ConnectionRefusedError:
                time.sleep(.01)
        else:
            raise RuntimeError("NATS startup timeout")
        if info["server_name"] != name or info["version"] != "2.11.9":
            raise RuntimeError("broker identity failed")
        yield port, proc.pid
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def jobs_for(p):
    u = p["unit_ns"]
    if type(u) is not int or not 100000<=u<=1000000000 or p["policy"] not in ("fifo","latest") or p["field"] not in ("none","one") or p["chosen_read"] not in (1,2):
        raise ValueError("unsupported plan")
    jobs = []
    for state in p["states"]:
        t, seq = state["offset_ns"], state["seq"]
        if type(t) is not int or not u<=t<=4*u or seq!=(1 if 2*t<5*u else 2):
            raise ValueError("invalid state release")
        jobs.append((t, b"S", seq))
    total = 0
    for i, event in enumerate(p["traffic"]):
        t, size = event["offset_ns"], event["size_bytes"]
        if type(t) is not int or not 0<=t<=4*u or type(size) is not int or not 0<=size<=65535:
            raise ValueError("invalid background")
        total += size
        if total>32*1024*1024: raise ValueError("background budget exceeded")
        payload = bytes.fromhex(event["payload_hex"]) if "payload_hex" in event else bytes([i%256])*size
        if len(payload)!=size: raise ValueError("payload size mismatch")
        jobs.append((t,b"B",payload))
    if len(jobs)>=65534: raise ValueError("message budget exceeded")
    return sorted(jobs,key=lambda j:j[0])


def hash_frame(h,kind,body):
    h.update(kind+ORDER.pack(len(body))+body)


def publisher(port, prefix, jobs, channel, samples, ready):
    try:
        with contextlib.closing(Client(port)) as c:
            c.publish(prefix+b".W", b"warm")
            if not channel.poll(6): raise RuntimeError("epoch handshake timed out")
            epoch = channel.recv()
            diag = []
            digest = hashlib.sha256()
            for ordinal,(release,kind,content) in enumerate(jobs):
                wait(epoch+release)
                if kind==b"S":
                    if not ready[content-1].wait(6): raise RuntimeError("sample unavailable")
                    body = ORDER.pack(ordinal)+STATE.pack(content,samples[content-1])
                    lo=NOW()-epoch
                    c.publish(prefix+b".S",body)
                    hi=NOW()-epoch
                    diag.append(dict(ordinal=ordinal,release_ns=release,send_lo_ns=lo,send_hi_ns=hi))
                else:
                    body=ORDER.pack(ordinal)+content
                    c.publish(prefix+b".B",body)
                hash_frame(digest,kind,body)
            c.publish(prefix+b".E",b"end")
            c.flush()
            channel.send(dict(digest=digest.hexdigest(),events=diag,pid=os.getpid()))
    except Exception as err:
        channel.send(dict(error=repr(err)))
    finally:
        channel.close()


def trial(p,port,broker_pid):
    start=NOW()
    jobs=jobs_for(p)
    prefix=b"window."+hashlib.sha256(p["run_id"].encode()).hexdigest()[:24].encode()
    m=mp.get_context("spawn") # no inherited subscriber or listening socket
    samples=m.RawArray("d", 2)
    ready=[m.Event(),m.Event()]
    ctl,child=m.Pipe()
    sub=Client(port)
    sub.sub(prefix+b".>")
    sender=m.Process(target=publisher,args=(port,prefix,jobs,child,samples,ready))
    sender.start()
    child.close()
    producer=None
    try:
        if sub.message()!=(prefix+b".W", b"warm"): raise RuntimeError("subscription warm-up failed")
        pending=collections.deque()
        lock=threading.Lock()
        ingress_diag={}
        receive_stats={}
        end_ingress=threading.Event()
        epoch=NOW()+2000000
        ctl.send(epoch)
        def now(): return NOW()-epoch
        def ingress():
            h=hashlib.sha256()
            n=0
            try:
                while True:
                    subject,body=sub.message()
                    kind=subject[len(prefix)+1:]
                    if subject == prefix+b".E" and body == b"end": break
                    if not subject.startswith(prefix+b".") or kind not in (b"S",b"B") or ORDER.unpack_from(body)[0]!=n:
                        raise RuntimeError("misrouted, lost or reordered broker stream")
                    if kind==b"S":
                        decoded=now()
                        state=STATE.unpack_from(body,ORDER.size)
                        with lock:
                            enlo=now()
                            pending.append(state)
                            enhi=now()
                        ingress_diag[n]=dict(recv_decoded_ns=decoded,enqueue_lo_ns=enlo,enqueue_hi_ns=enhi)
                    hash_frame(h,kind,body)
                    n+=1
                receive_stats.update(received=n,digest=h.hexdigest())
            except Exception as err:
                receive_stats["error"]=repr(err)
            finally:
                end_ingress.set()
        worker=threading.Thread(target=ingress)
        worker.start()
        row={k:v for k,v in p.items() if k not in ("states","traffic")}
        x,u,prev,minimum=1.,-.5,0,1.
        unit=p["unit_ns"]
        def advance(t):
            nonlocal x,prev,minimum
            x+=u*((t-prev)/unit); prev=t; minimum=min(minimum,x)
        sink=bytearray(4)
        field=write_field if p["field"]=="one" else sham_field
        selected=(0,1.)
        reads=[]
        for i in (1,2):
            wait(epoch+(unit if i==1 else 5*unit//2))
            t=now(); advance(t); samples[i-1]=x; ready[i-1].set()
            row[f"s{i}_ns"],row[f"s{i}"]=t,x
            wait(epoch+(i+1)*unit)
            lo=now()
            with lock:
                cut=now()
                if pending:
                    if p["policy"]=="fifo":
                        selected=pending.popleft()
                    else:
                        selected=pending[-1]
                        pending.clear()
                hi=now()
            next_u=-selected[1]
            apply=now(); advance(apply); u=next_u
            row[f"apply{i}_ns"],row[f"u{i}"],row[f"x_read{i}"]=apply,u,x
            reads.append(dict(read=i,lo_ns=lo,cut_ns=cut,hi_ns=hi))
            if i==p["chosen_read"]:
                row["field_lo_ns"]=now()
                field(sink,selected[0])
                row["field_hi_ns"]=now()
        wait(epoch+4*unit)
        end=now(); advance(end)
        if not end_ingress.wait(8) or not ctl.poll(8): raise RuntimeError("broker drain timeout")
        producer=ctl.recv()
        if "error" in producer or "error" in receive_stats:
            raise RuntimeError((producer,receive_stats))
        if producer["digest"]!=receive_stats["digest"] or receive_stats["received"]!=len(jobs):
            raise RuntimeError("sender/subscriber count or digest differs")
        for ev in producer["events"]:
            ev.update(ingress_diag[ev["ordinal"]])
        sink_bytes=bytes(sink) if p["field"]=="one" else b""
        row.update(x_min=minimum,x_end=x,end_ns=end,field_bytes=len(sink_bytes),field_hex=sink_bytes.hex(),
                   state_messages=len(p["states"]),traffic_messages=len(p["traffic"]),sent=len(jobs),
                   received=receive_stats["received"],stream_sha256=receive_stats["digest"],integrity=True,
                   subscription_ready=True,broker="NATS Core 2.11.9",kernel=platform.release(),
                   clock_guard_ns=math.ceil(time.get_clock_info("monotonic").resolution*1e9)+1,
                   diagnostics=dict(state_events=producer["events"],reads=reads,broker_pid=broker_pid,
                                    publisher_pid=producer["pid"],subscriber_pid=os.getpid()),
                   trial_wall_ns=NOW()-start)
        return row
    finally:
        if producer is None and sender.is_alive(): sender.terminate()
        sender.join(timeout=2)
        if sender.is_alive(): sender.kill(); sender.join()
        if 'worker' in locals() and worker.is_alive():
            try: sub.sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            worker.join(timeout=7)
        sub.close(); ctl.close()


def main():
    if len(sys.argv)!=3: raise SystemExit("deployment.py PLAN.jsonl NEW_OUTPUT.jsonl")
    binary=Path(os.environ.get("NATS_SERVER",DEFAULT_BIN))
    dest=Path(sys.argv[2]); part=dest.with_name(dest.name+".part")
    if dest.exists(): raise FileExistsError(dest)
    with broker(binary) as (port,pid), Path(sys.argv[1]).open() as plan, part.open("x") as out:
        for line in plan:
            if line.strip():
                out.write(json.dumps(trial(json.loads(line),port,pid),allow_nan=False)+"\n")
                out.flush()
    part.rename(dest)


if __name__=="__main__":
    main()
