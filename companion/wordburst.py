"""On-device speech recognition for Wordburst. The bar receives counts, never audio."""
import argparse
import collections
from contextlib import nullcontext
import json
import math
import queue
import re
import subprocess
import sys
import tempfile
import threading
import unicodedata
import uuid
import wave
from array import array
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RATE = 16000
FRAME = 640  # 20 milliseconds, mono, signed 16-bit little endian

class Counter:
    def __init__(self, word):
        self.word = unicodedata.normalize("NFC", word).strip()
        if not self.word or len(self.word) > 40:
            raise ValueError("Use a word or phrase between 1 and 40 characters.")
        self.pattern = re.compile(r"(?<!\w)" + re.escape(self.word.casefold()) + r"(?!\w)")
        self.session = uuid.uuid4().hex[:12]
        self.count = 0
        self.state = "Listening"
        self.lock = threading.Lock()

    def add(self, transcript):
        matches = len(self.pattern.findall(unicodedata.normalize("NFC", transcript).casefold()))
        with self.lock:
            self.count += matches
        print("Matches in utterance:", matches, flush=True)

    def set_state(self, text):
        with self.lock:
            self.state = text

    def snapshot(self):
        with self.lock:
            return dict(session=self.session, count=self.count, word=self.word, state=self.state)

def recognize(path, args, counter):
    with tempfile.TemporaryDirectory() as tmp:
        prefix = str(Path(tmp) / "result")
        subprocess.run([args.whisper, "-m", args.model, "-f", str(path), "-l", args.language,
                        "-otxt", "-of", prefix, "-nt", "-np"], stdout=subprocess.DEVNULL, check=True)
        counter.add(Path(prefix + ".txt").read_text(encoding="utf-8"))

def utterances(stream, floor):
    lead = collections.deque(maxlen=12)
    frames = []
    silence = 0
    while True:
        frame = stream.read(FRAME)
        if len(frame) != FRAME:
            if frames:
                yield b"".join(frames)
            break
        pcm = array("h", frame)
        if sys.byteorder != "little":
            pcm.byteswap()
        rms = math.sqrt(sum(v*v for v in pcm) / len(pcm))
        if not frames:
            lead.append(frame)
            if rms >= floor:
                frames = list(lead)
                lead.clear()
        else:
            frames.append(frame)
            silence = silence + 1 if rms < floor else 0
            if silence >= 28 or len(frames) >= 600:
                yield b"".join(frames)
                frames, silence = [], 0

def microphone(args, counter, stop):
    chunks = queue.Queue(maxsize=5)
    source = (nullcontext(None) if args.pcm_stdin else subprocess.Popen(
        ["ffmpeg","-nostdin","-loglevel","error","-f","avfoundation","-i",":"+args.microphone,
         "-ac","1","-ar",str(RATE),"-f","s16le","pipe:1"],stdout=subprocess.PIPE))
    with source as capture:
        stream = sys.stdin.buffer if args.pcm_stdin else capture.stdout
        def consume():
            while not stop.is_set():
                try: pcm = chunks.get(timeout=0.3)
                except queue.Empty: continue
                if pcm is None: return
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "utterance.wav"
                    with wave.open(str(path),"wb") as out:
                        out.setparams((1,2,RATE,0,"NONE","not compressed"));out.writeframes(pcm)
                    try: recognize(path,args,counter)
                    except (OSError,subprocess.CalledProcessError) as error:
                        counter.set_state("Decoder error")
                        print(type(error).__name__, file=sys.stderr)
        worker = threading.Thread(target=consume,daemon=True);worker.start()
        try:
            for utterance in utterances(stream,args.floor):
                if stop.is_set(): break
                try: chunks.put_nowait(utterance)
                except queue.Full: counter.set_state("Decoder overloaded")
        finally:
            if capture is not None: capture.terminate()
            chunks.put(None)
            worker.join()
            counter.set_state("Input ended")

def serve(args, counter):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/wordburst":
                self.send_error(404);return
            payload = json.dumps(counter.snapshot()).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(payload)));self.end_headers()
            self.wfile.write(payload)
        def log_message(self,*args): pass
    stop = threading.Event()
    def work():
        try:
            if args.wav:
                recognize(args.wav,args,counter);counter.set_state("Recording finished")
            else: microphone(args,counter,stop)
        except (OSError,subprocess.CalledProcessError) as error:
            counter.set_state("Source error");print(type(error).__name__,file=sys.stderr)
    with ThreadingHTTPServer((args.host,args.port),Handler) as server:
        threading.Thread(target=work,daemon=True).start()
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: stop.set()

if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument("--pcm-stdin", action="store_true",help="Read continuous 16 kHz mono signed 16-bit little-endian audio on stdin")
    source.add_argument("--wav",type=Path,help="16 kHz mono PCM recording")
    source.add_argument("--microphone",help="macOS AVFoundation audio input index")
    p.add_argument("--model",required=True,help="Path to a whisper.cpp model")
    p.add_argument("--whisper",default="whisper-cli");p.add_argument("--word",required=True)
    p.add_argument("--language",default="en");p.add_argument("--floor",type=int,default=260)
    p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8770)
    cfg=p.parse_args();serve(cfg,Counter(cfg.word))
