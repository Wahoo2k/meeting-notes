"""Reads Teams live captions off the screen through Windows UI Automation (the accessibility
interface screen readers use). Live captions show only on your own screen.

The output is a timeline of (seconds_since_start, speaker_name, caption_text) observations,
used later to put names on transcript lines. Teams changes its layout from time to time, so
the parsing here is heuristic; `dump_teams_tree` writes the raw structure to a file so the
parser can be tuned.
"""
import re
import threading
import time

CAPTION_HINTS = ("caption",)
MAX_SEARCH_DEPTH = 40


def _is_teams_window(ctrl) -> bool:
    try:
        import psutil

        name = psutil.Process(ctrl.ProcessId).name().lower()
        if "teams" in name:
            return True
    except Exception:
        pass
    try:
        return "microsoft teams" in (ctrl.Name or "").lower()
    except Exception:
        return False


def teams_windows():
    import uiautomation as auto

    out = []
    for w in auto.GetRootControl().GetChildren():
        if _is_teams_window(w):
            out.append(w)
    return out


def meeting_title():
    """Best guess at the meeting name from the Teams window title."""
    try:
        for w in teams_windows():
            name = (w.Name or "").strip()
            if name and name.lower() not in ("microsoft teams", ""):
                return re.sub(r"\s*\|\s*Microsoft Teams.*$", "", name).strip()
    except Exception:
        pass
    return ""


def _walk(ctrl, depth=0, max_depth=MAX_SEARCH_DEPTH):
    yield ctrl, depth
    if depth >= max_depth:
        return
    try:
        children = ctrl.GetChildren()
    except Exception:
        return
    for c in children:
        yield from _walk(c, depth + 1, max_depth)


def _label(ctrl):
    try:
        return " ".join(
            x for x in [(ctrl.Name or ""), (ctrl.AutomationId or ""), (ctrl.ClassName or "")] if x
        ).lower()
    except Exception:
        return ""


def find_caption_container():
    for w in teams_windows():
        for ctrl, _ in _walk(w):
            lab = _label(ctrl)
            if any(h in lab for h in CAPTION_HINTS) and ctrl.ControlTypeName in (
                "ListControl", "GroupControl", "PaneControl", "CustomControl", "DocumentControl",
            ):
                try:
                    if ctrl.GetChildren():
                        return ctrl
                except Exception:
                    continue
    return None


_NAME_RE = re.compile(r"^[A-Z][\w'.\-]*(\s+[A-Z(][\w'.\-()]*){0,4}$")


def _looks_like_name(s: str) -> bool:
    s = s.strip()
    return 0 < len(s) <= 50 and len(s.split()) <= 5 and bool(_NAME_RE.match(s)) and not s.endswith(".")


def parse_entries(container):
    """Return [(speaker, text)] currently visible in the captions area."""
    entries = []
    items = []
    try:
        items = container.GetChildren()
    except Exception:
        return entries
    for item in items:
        texts = []
        for ctrl, _ in _walk(item, max_depth=8):
            if ctrl.ControlTypeName == "TextControl":
                t = (ctrl.Name or "").strip()
                if t and (not texts or texts[-1] != t):
                    texts.append(t)
        if not texts:
            whole = (item.Name or "").strip()
            if ": " in whole:
                spk, txt = whole.split(": ", 1)
                if _looks_like_name(spk):
                    entries.append((spk.strip(), txt.strip()))
            continue
        if len(texts) >= 2 and _looks_like_name(texts[0]):
            entries.append((texts[0], " ".join(texts[1:])))
        elif entries and len(texts) == 1:
            # continuation line from the same speaker as the previous item
            spk, prev = entries[-1]
            entries[-1] = (spk, prev + " " + texts[0])
    return entries


class CaptionWatcher(threading.Thread):
    def __init__(self, t0_monotonic, poll_seconds=1.0):
        super().__init__(daemon=True, name="captions")
        self.t0 = t0_monotonic
        self.poll = poll_seconds
        self._stop_event = threading.Event()
        self.observations = []  # (t, speaker, text)
        self.found_container = False
        self.error = None
        self._last = {}

    def stop(self):
        self._stop_event.set()
        self.join(timeout=5)

    def run(self):
        try:
            import uiautomation as auto
        except Exception as e:
            self.error = f"uiautomation unavailable: {e}"
            return
        with auto.UIAutomationInitializerInThread():
            container = None
            next_search = 0.0
            while not self._stop_event.is_set():
                now = time.monotonic()
                try:
                    if container is None and now >= next_search:
                        container = find_caption_container()
                        next_search = now + 5
                        if container is not None:
                            self.found_container = True
                    if container is not None:
                        entries = parse_entries(container)
                        if not entries and not container.Exists(0, 0):
                            container = None
                        t = now - self.t0
                        for spk, txt in entries:
                            key = (spk, txt[:40])
                            if self._last.get(key) != txt:
                                self._last[key] = txt
                                self.observations.append((t, spk, txt))
                except Exception as e:
                    self.error = f"{type(e).__name__}: {e}"
                    container = None
                self._stop_event.wait(self.poll)


def dump_teams_tree(path, max_depth=MAX_SEARCH_DEPTH):
    """Write the Teams UI structure to a text file (used by the probe to tune parsing)."""
    import uiautomation as auto

    with auto.UIAutomationInitializerInThread():
        wins = teams_windows()
        with open(path, "w", encoding="utf-8") as f:
            if not wins:
                f.write("No Teams windows found.\n")
                return 0
            count = 0
            for w in wins:
                for ctrl, depth in _walk(w, max_depth=max_depth):
                    try:
                        f.write(
                            "  " * depth
                            + f"{ctrl.ControlTypeName} | name={ctrl.Name!r} | id={ctrl.AutomationId!r} | class={ctrl.ClassName!r}\n"
                        )
                        count += 1
                    except Exception:
                        continue
            return count
