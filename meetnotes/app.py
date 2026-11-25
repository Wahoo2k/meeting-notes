"""System-tray app: watches for Teams calls, records them, writes meeting notes."""
import logging
import os
import queue
import subprocess
import sys
import threading
import time

from .config import Config, data_dir
from .detect import apps_using_mic, teams_call_active
from .session import Session

log = logging.getLogger("meetnotes")


def _setup_logging():
    path = os.path.join(data_dir(), "meetnotes.log")
    logging.basicConfig(
        filename=path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def _icon(recording: bool, busy: bool = False):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((6, 10, 58, 54), radius=10, fill=(40, 90, 160, 255))
    for i, y in enumerate((20, 30, 40)):
        d.line((16, y, 48 - i * 8, y), fill=(255, 255, 255, 255), width=4)
    if recording:
        d.ellipse((40, 36, 62, 58), fill=(220, 40, 40, 255), outline=(255, 255, 255, 255), width=2)
    elif busy:
        d.ellipse((40, 36, 62, 58), fill=(240, 170, 20, 255), outline=(255, 255, 255, 255), width=2)
    return img


class App:
    def __init__(self):
        self.cfg = Config.load()
        self.work_dir = os.path.join(data_dir(), "recordings")
        self.session = None
        self.manual = False
        self.paused = False
        self.status = "Waiting for a Teams call"
        self.jobs = queue.Queue()
        self.icon = None
        self._quit = threading.Event()

    # ---- recording control
    def start_recording(self, manual=False):
        if self.session:
            return
        self.session = Session(self.cfg, self.work_dir)
        self.manual = manual
        self.session.start()
        self._set_status("Recording", recording=True)

    def stop_recording(self):
        s, self.session = self.session, None
        if not s:
            return
        duration, obs, notes = s.stop()
        if duration < self.cfg.min_call_seconds and not self.manual:
            log.info("Call under %ss, discarded", self.cfg.min_call_seconds)
            for p in (s.mic_path, s.sys_path):
                try:
                    os.remove(p)
                except OSError:
                    pass
            self._set_status("Waiting for a Teams call")
            return
        self.jobs.put((s, duration, obs, notes))
        self._set_status(f"Transcribing ({self.jobs.qsize()} queued)", busy=True)

    # ---- background loops
    def _monitor(self):
        last_active = 0.0
        last_users = None
        while not self._quit.is_set():
            try:
                users = apps_using_mic()
                if users != last_users:
                    log.info("apps using mic: %s", users or "none")
                    last_users = users
                active = teams_call_active(self.cfg.teams_markers)
            except Exception as e:
                log.warning("detect failed: %s", e)
                active = False
            now = time.monotonic()
            if active:
                last_active = now
            if self.cfg.auto_record and not self.paused:
                if active and not self.session:
                    self.start_recording()
                elif self.session and not self.manual and not active and now - last_active > self.cfg.end_grace_seconds:
                    self.stop_recording()
            self._quit.wait(2)

    def _worker(self):
        while not self._quit.is_set():
            try:
                s, duration, obs, notes = self.jobs.get(timeout=1)
            except queue.Empty:
                continue
            try:
                path = s.process(duration, obs, notes)
                self._notify("Meeting notes ready", os.path.basename(path))
            except Exception as e:
                log.exception("processing failed")
                self._notify("Meeting notes failed", str(e)[:200])
            if not self.session:
                self._set_status("Waiting for a Teams call" if self.jobs.empty() else "Transcribing", busy=not self.jobs.empty())

    # ---- tray UI
    def _set_status(self, text, recording=False, busy=False):
        self.status = text
        log.info("status: %s", text)
        if self.icon:
            self.icon.icon = _icon(recording, busy)
            self.icon.title = f"Meeting Notes - {text}"
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def _notify(self, title, msg):
        try:
            if self.icon:
                self.icon.notify(msg, title)
        except Exception:
            pass

    def _open_folder(self, *_):
        os.makedirs(self.cfg.output_dir, exist_ok=True)
        os.startfile(self.cfg.output_dir)  # noqa: windows only

    def _open_logs(self, *_):
        os.startfile(data_dir())  # noqa: windows only

    def _open_config(self, *_):
        subprocess.Popen(["notepad.exe", self.cfg.path])

    def _toggle_pause(self, *_):
        self.paused = not self.paused

    def _toggle_record(self, *_):
        if self.session:
            self.stop_recording()
        else:
            self.start_recording(manual=True)

    def _quit_app(self, icon, *_):
        if self.session:
            self.stop_recording()
        self._notify("Meeting Notes", "Finishing any transcriptions, then closing.")
        while not self.jobs.empty():
            time.sleep(1)
        self._quit.set()
        icon.stop()

    def run(self):
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem(lambda _: self.status, None, enabled=False),
            pystray.MenuItem(lambda _: "Stop recording" if self.session else "Record now", self._toggle_record),
            pystray.MenuItem("Pause auto-record", self._toggle_pause, checked=lambda _: self.paused),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open notes folder", self._open_folder),
            pystray.MenuItem("Settings", self._open_config),
            pystray.MenuItem("Open log folder", self._open_logs),
            pystray.MenuItem("Quit", self._quit_app),
        )
        self.icon = pystray.Icon("meetnotes", _icon(False), "Meeting Notes", menu)
        threading.Thread(target=self._monitor, daemon=True).start()
        threading.Thread(target=self._worker, daemon=True).start()
        self.icon.run()


def main():
    _setup_logging()
    if sys.platform != "win32":
        print("Meeting Notes runs on Windows.")
        return
    # Load the Windows accessibility library once, up front. Loading it from two threads
    # at the same time on first run corrupts its generated helper files.
    try:
        import uiautomation  # noqa: F401
    except Exception:
        log.exception("uiautomation failed to load")
    App().run()


if __name__ == "__main__":
    main()
