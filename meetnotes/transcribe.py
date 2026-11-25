"""Local speech-to-text with faster-whisper (runs on CPU, nothing leaves the PC)."""
import os

_model_cache = {}


def load_model(name, model_dir):
    from faster_whisper import WhisperModel

    key = (name, model_dir)
    if key not in _model_cache:
        os.makedirs(model_dir, exist_ok=True)
        threads = max(1, (os.cpu_count() or 4) - 1)
        _model_cache[key] = WhisperModel(
            name, device="cpu", compute_type="int8", download_root=model_dir, cpu_threads=threads
        )
    return _model_cache[key]


def transcribe(path, model):
    """Return [{'start','end','text'}] for one audio file."""
    if not os.path.exists(path) or os.path.getsize(path) < 2000:
        return []
    segments, _info = model.transcribe(
        path,
        language="en",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=5,
        condition_on_previous_text=False,
    )
    out = []
    for s in segments:
        text = s.text.strip()
        if text:
            out.append({"start": float(s.start), "end": float(s.end), "text": text})
    return out
