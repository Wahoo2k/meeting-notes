"""Feasibility test. Run it once during a Teams call (live captions on) and it writes
probe_report.txt next to itself. Records 30 seconds; nothing is uploaded anywhere.
"""
import os
import platform
import sys
import time
import traceback

from .config import app_dir


def main():
    out_dir = os.path.join(app_dir(), "probe_output")
    os.makedirs(out_dir, exist_ok=True)
    report = []

    def say(line=""):
        print(line)
        report.append(line)

    say("MEETING NOTES FEASIBILITY TEST")
    say(f"Windows: {platform.platform()}  Python: {sys.version.split()[0]}  CPUs: {os.cpu_count()}")
    say("Join a Teams call (a test call with yourself is fine) and turn on live captions.")
    say("Talk, or play some audio, during the 30 seconds.")
    say()

    # 1. Call detection
    try:
        from .detect import apps_using_mic, teams_call_active

        say(f"[1] Apps using mic right now: {apps_using_mic() or 'none'}")
        say(f"[1] Teams call detected: {'YES' if teams_call_active() else 'NO'}")
    except Exception as e:
        say(f"[1] Call detection FAILED: {e}")

    # 2. Caption reading (structure dump)
    try:
        from . import captions as cap

        n = cap.dump_teams_tree(os.path.join(out_dir, "teams_tree.txt"))
        say(f"[2] Teams UI elements readable: {n}")
        say(f"[2] Meeting title: {cap.meeting_title()!r}")
    except Exception as e:
        say(f"[2] Reading Teams window FAILED: {e}")

    # 3. Record 30s of both tracks while watching captions
    try:
        from .recorder import Recorder
        from .captions import CaptionWatcher

        mic = os.path.join(out_dir, "test_mic.wav")
        sysp = os.path.join(out_dir, "test_system.wav")
        rec = Recorder(mic, sysp)
        rec.start()
        watcher = CaptionWatcher(rec.t0)
        watcher.start()
        for i in range(30, 0, -5):
            print(f"    recording... {i}s left")
            time.sleep(5)
        errors = rec.stop()
        watcher.stop()
        for t in rec.tracks:
            secs = t.frames_written / 16000
            level = "has sound" if t.peak > 0.01 else "SILENT"
            say(f"[3] {t.label} track: {secs:.0f}s recorded, {level} (peak {t.peak:.3f})"
                + (f" ERROR {errors[t.label]}" if t.label in errors else ""))
        say(f"[3] Caption area found: {'YES' if watcher.found_container else 'NO'}"
            + (f" (error: {watcher.error})" if watcher.error else ""))
        speakers = sorted({o[1] for o in watcher.observations})
        say(f"[3] Caption lines captured: {len(watcher.observations)}; speakers seen: {speakers or 'none'}")
        for o in watcher.observations[-5:]:
            say(f"      {o[0]:5.1f}s  {o[1]}: {o[2][:80]}")
    except Exception:
        say("[3] Recording FAILED:")
        say(traceback.format_exc())

    path = os.path.join(app_dir(), "probe_report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    say()
    say(f"Done. Report saved to {path}")
    say("Send back probe_report.txt (and probe_output\\teams_tree.txt if captions said NO).")
    input("Press Enter to close.")


if __name__ == "__main__":
    main()
