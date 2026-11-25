"""Records two tracks: your microphone, and everything the PC plays (the other people).

Uses WASAPI loopback through the `soundcard` package, so no driver or admin rights are needed.
Each track is padded with silence when the device sends nothing, so both stay aligned to
wall-clock time from the moment recording started.
"""
import threading
import time
import wave
import warnings

import numpy as np

RATE = 16000
BLOCK_SECONDS = 0.5


def _to_int16(frames: np.ndarray) -> bytes:
    if frames.ndim > 1:
        frames = frames.mean(axis=1)
    frames = np.clip(frames, -1.0, 1.0)
    return (frames * 32767).astype(np.int16).tobytes()


class _Track(threading.Thread):
    def __init__(self, label, get_device, path, stop_event, t0):
        super().__init__(daemon=True, name=f"rec-{label}")
        self.label = label
        self.get_device = get_device
        self.path = path
        self.stop_event = stop_event
        self.t0 = t0
        self.error = None
        self.frames_written = 0
        self.peak = 0.0

    def run(self):
        import soundcard as sc  # imported here so the rest of the app loads anywhere

        warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)
        block = int(RATE * BLOCK_SECONDS)
        try:
            device = self.get_device(sc)
            with wave.open(self.path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(RATE)
                with device.recorder(samplerate=RATE, channels=1, blocksize=block) as rec:
                    while not self.stop_event.is_set():
                        data = rec.record(numframes=block)
                        # Pad with silence if the device went quiet and we fell behind real time.
                        expected = int((time.monotonic() - self.t0) * RATE)
                        behind = expected - (self.frames_written + len(data))
                        if behind > RATE * 0.25:
                            wf.writeframes(b"\x00\x00" * behind)
                            self.frames_written += behind
                        if len(data):
                            self.peak = max(self.peak, float(np.abs(data).max()))
                            wf.writeframes(_to_int16(data))
                            self.frames_written += len(data)
        except Exception as e:  # surfaced to the UI / probe
            self.error = f"{type(e).__name__}: {e}"


def _mic(sc):
    return sc.default_microphone()


def _loopback(sc):
    return sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True)


class Recorder:
    def __init__(self, mic_path, sys_path):
        self.mic_path = mic_path
        self.sys_path = sys_path
        self._stop = threading.Event()
        self.tracks = []
        self.started_at = None  # wall-clock epoch seconds

    def start(self):
        t0 = time.monotonic()
        self.started_at = time.time()
        self.t0 = t0
        self.tracks = [
            _Track("mic", _mic, self.mic_path, self._stop, t0),
            _Track("system", _loopback, self.sys_path, self._stop, t0),
        ]
        for t in self.tracks:
            t.start()

    def elapsed(self):
        return time.monotonic() - self.t0 if self.started_at else 0.0

    def stop(self):
        self._stop.set()
        for t in self.tracks:
            t.join(timeout=5)
        return {t.label: t.error for t in self.tracks if t.error}
