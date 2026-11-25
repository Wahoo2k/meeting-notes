"""Combines the two transcripts and the caption timeline into one named transcript.

Pure Python with no Windows dependencies, so it can be unit-tested anywhere.
"""
import re
from datetime import datetime

OTHER = "Other"


def words(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def overlap(segment_text, caption_text):
    """Fraction of the segment's words that also appear in the caption text."""
    seg = words(segment_text)
    if not seg:
        return 0.0
    cap = set(words(caption_text))
    return sum(1 for w in seg if w in cap) / len(seg)


def assign_names(sys_segments, observations, before=4.0, after=12.0, min_score=0.35):
    """Label each system-audio segment with the caption speaker whose words best match.

    observations: [(t_seconds, speaker, caption_text)]. Captions lag the audio by a few
    seconds and grow as people talk, so we look in a window after the segment too.
    """
    labeled = []
    for seg in sys_segments:
        lo, hi = seg["start"] - before, seg["end"] + after
        best, best_score = None, 0.0
        for t, spk, txt in observations:
            if lo <= t <= hi:
                sc = overlap(seg["text"], txt)
                if sc > best_score:
                    best, best_score = spk, sc
        name = best if best_score >= min_score else None
        labeled.append({**seg, "speaker": name})

    # Fill gaps: an unmatched segment sandwiched by the same speaker, or adjacent within 3s,
    # probably belongs to that speaker.
    for i, seg in enumerate(labeled):
        if seg["speaker"]:
            continue
        prev = labeled[i - 1] if i > 0 else None
        nxt = labeled[i + 1] if i + 1 < len(labeled) else None
        if prev and nxt and prev["speaker"] and prev["speaker"] == nxt["speaker"]:
            seg["speaker"] = prev["speaker"]
        elif prev and prev["speaker"] and seg["start"] - prev["end"] < 3.0:
            seg["speaker"] = prev["speaker"]
        else:
            seg["speaker"] = OTHER
    return labeled


def drop_bleed(mic_segments, sys_segments, min_score=0.6):
    """Remove mic segments that are just the other people's audio leaking from your speakers."""
    kept = []
    for m in mic_segments:
        leak = False
        for s in sys_segments:
            if s["start"] - 2 <= m["start"] <= s["end"] + 2 and overlap(m["text"], s["text"]) >= min_score:
                leak = True
                break
        if not leak:
            kept.append(m)
    return kept


def build_transcript(mic_segments, sys_segments, observations, my_name="Me", merge_gap=2.0):
    mic = [{**m, "speaker": my_name} for m in drop_bleed(mic_segments, sys_segments)]
    others = assign_names(sys_segments, observations)
    allsegs = sorted(mic + others, key=lambda s: s["start"])

    lines = []
    for s in allsegs:
        if lines and lines[-1]["speaker"] == s["speaker"] and s["start"] - lines[-1]["end"] <= merge_gap:
            lines[-1]["text"] += " " + s["text"]
            lines[-1]["end"] = s["end"]
        else:
            lines.append({"start": s["start"], "end": s["end"], "speaker": s["speaker"], "text": s["text"]})
    return lines


def _ts(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def to_markdown(lines, started_at: datetime, duration_s: float, title: str = "", notes=None):
    speakers = []
    for l in lines:
        if l["speaker"] not in speakers:
            speakers.append(l["speaker"])
    head = title or "Meeting"
    out = [
        f"# {head}",
        "",
        f"- Date: {started_at:%A, %B %d, %Y}",
        f"- Start: {started_at:%I:%M %p}".replace(" 0", " "),
        f"- Length: {int(duration_s // 60)} min",
        f"- Speakers: {', '.join(speakers) if speakers else 'none detected'}",
    ]
    for n in notes or []:
        out.append(f"- Note: {n}")
    out += ["", "## Transcript", ""]
    for l in lines:
        out.append(f"**[{_ts(l['start'])}] {l['speaker']}:** {l['text']}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
