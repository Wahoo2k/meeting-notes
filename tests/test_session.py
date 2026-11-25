import os
import wave
from datetime import datetime
from types import SimpleNamespace

import meetnotes.session as sess
from meetnotes.config import Config


class FakeModel:
    def transcribe(self, path, **kw):
        if path.endswith("_mic.wav"):
            segs = [SimpleNamespace(start=1.0, end=3.0, text=" Morning everyone.")]
        else:
            segs = [SimpleNamespace(start=4.0, end=7.0, text=" Morning, the renewal list is ready.")]
        return iter(segs), None


def _wav(path):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)


def test_process_writes_notes(tmp_path, monkeypatch):
    monkeypatch.setattr(sess, "load_model", lambda *a: FakeModel())
    cfg = Config(output_dir=str(tmp_path / "out"), model_dir=str(tmp_path / "m"), my_name="Tom")
    s = sess.Session(cfg, str(tmp_path / "rec"))
    s.started = datetime(2026, 12, 1, 10, 0)
    s.title = "Weekly pricing"
    _wav(s.mic_path); _wav(s.sys_path)
    out = s.process(600, [(6.0, "Sarah Jones", "Morning, the renewal list is ready.")], [])
    md = open(out, encoding="utf-8").read()
    assert os.path.basename(out).startswith("meeting_notes_")
    assert "**[00:00:01] Tom:** Morning everyone." in md
    assert "**[00:00:04] Sarah Jones:** Morning, the renewal list is ready." in md
    assert not os.path.exists(s.mic_path)  # audio cleaned up
