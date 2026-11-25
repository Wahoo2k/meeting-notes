"""Settings, stored as config.json next to the program."""
import json
import os
import sys
from dataclasses import dataclass, asdict, field


def app_dir() -> str:
    """Folder the program lives in (works for source and PyInstaller builds)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_output_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "Documents", "meeting_notes")


@dataclass
class Config:
    # Where finished notes are written. Point this at the folder your Claude task process reads.
    output_dir: str = field(default_factory=default_output_dir)
    # Whisper model: tiny.en, base.en, small.en, medium.en. Bigger = more accurate, slower.
    model: str = "small.en"
    # Folder holding downloaded models (copy a model here manually if downloads are blocked).
    model_dir: str = field(default_factory=lambda: os.path.join(app_dir(), "models"))
    # Start/stop recording automatically when Teams is using the microphone.
    auto_record: bool = True
    # Seconds Teams must release the mic before we treat the call as over.
    end_grace_seconds: int = 15
    # Ignore calls shorter than this (seconds).
    min_call_seconds: int = 60
    # Read Teams live captions to put names on speakers.
    read_captions: bool = True
    # Keep the raw .wav recordings after transcribing.
    keep_audio: bool = False
    # Your name as it should appear in the transcript.
    my_name: str = "Me"
    # Process names that count as Teams.
    teams_markers: list = field(default_factory=lambda: ["teams"])

    @property
    def path(self) -> str:
        return os.path.join(app_dir(), "config.json")

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if os.path.exists(cfg.path):
            try:
                with open(cfg.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
            except Exception:
                pass
        else:
            cfg.save()
        return cfg

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except Exception:
            pass
