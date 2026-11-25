"""One meeting: record, watch captions, then transcribe and write the notes file."""
import json
import logging
import os
import time
from datetime import datetime

from . import captions as cap
from .merge import build_transcript, to_markdown
from .recorder import Recorder
from .transcribe import load_model, transcribe

log = logging.getLogger("meetnotes")


class Session:
    def __init__(self, cfg, work_dir):
        self.cfg = cfg
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        self.stamp = stamp
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)
        self.mic_path = os.path.join(work_dir, f"{stamp}_mic.wav")
        self.sys_path = os.path.join(work_dir, f"{stamp}_system.wav")
        self.recorder = Recorder(self.mic_path, self.sys_path)
        self.watcher = None
        self.title = ""
        self.started = None

    def start(self):
        self.started = datetime.now()
        self.recorder.start()
        if self.cfg.read_captions:
            self.watcher = cap.CaptionWatcher(self.recorder.t0)
            self.watcher.start()
        try:
            self.title = cap.meeting_title()
        except Exception:
            self.title = ""
        log.info("Recording started %s (%s)", self.stamp, self.title)

    def stop(self):
        errors = self.recorder.stop()
        duration = self.recorder.elapsed()
        obs = []
        notes = []
        if self.watcher:
            self.watcher.stop()
            obs = self.watcher.observations
            if not self.watcher.found_container:
                notes.append("Teams captions weren't found, so other speakers aren't named. Turn on live captions in the meeting.")
            if self.watcher.error:
                log.warning("Caption watcher: %s", self.watcher.error)
        for k, v in errors.items():
            log.error("%s track error: %s", k, v)
            notes.append(f"{k} audio had a problem: {v}")
        log.info("Recording stopped after %.0fs, %d caption observations", duration, len(obs))
        return duration, obs, notes

    def process(self, duration, obs, notes):
        """Transcribe and write the notes file. Returns its path."""
        t = time.time()
        model = load_model(self.cfg.model, self.cfg.model_dir)
        mic = transcribe(self.mic_path, model)
        sysa = transcribe(self.sys_path, model)
        lines = build_transcript(mic, sysa, obs, my_name=self.cfg.my_name)
        md = to_markdown(lines, self.started, duration, self.title, notes)

        os.makedirs(self.cfg.output_dir, exist_ok=True)
        out_path = os.path.join(self.cfg.output_dir, f"meeting_notes_{self.stamp}.md")
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(md)
        os.replace(tmp, out_path)  # appears all at once so watchers never see half a file

        # Raw caption log kept beside the audio for tuning name matching.
        with open(os.path.join(self.work_dir, f"{self.stamp}_captions.json"), "w", encoding="utf-8") as f:
            json.dump(obs, f)
        if not self.cfg.keep_audio:
            for p in (self.mic_path, self.sys_path):
                try:
                    os.remove(p)
                except OSError:
                    pass
        log.info("Wrote %s in %.0fs", out_path, time.time() - t)
        return out_path
