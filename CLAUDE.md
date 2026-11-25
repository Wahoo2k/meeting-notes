# Meeting Notes: developer handoff

Read this before changing code. (CLAUDE_INSTRUCTIONS.md is a different file: it tells Claude how
to summarize the transcripts this app produces, not how to develop it.)

## What this is

A Windows system-tray app (Python, packaged with PyInstaller) that records Microsoft Teams
calls on the user's own work PC, transcribes them locally with faster-whisper, labels who said
what, and writes `meeting_notes_YYYY-MM-DD_HHMM.md` files. Hard constraints:
- No admin rights, no drivers, no installers, no bots joining calls, nothing leaves the PC.
- Must not require Teams transcription/recording to be turned on.
- Settings, logs, recordings and models live in `%LOCALAPPDATA%\MeetingNotes` (Documents is
  OneDrive-synced at work). Notes are written to `output_dir` (default `Documents\meeting_notes`).

## Layout

- `meetnotes/__init__.py` sets `sys.coinit_flags = 0` (MTA) before anything imports comtypes.
  soundcard and uiautomation both use COM and crash if apartments conflict. Keep this.
- `config.py` dataclass settings saved as `config.json` in the data dir. `data_dir()` / `app_dir()`.
- `detect.py` reads `HKCU\...\CapabilityAccessManager\ConsentStore\microphone` (packaged apps and
  `NonPackaged`); an entry with `LastUsedTimeStop == 0` is using the mic now. A Teams call = an entry
  whose key name contains a `teams_markers` string.
- `recorder.py` records two 16 kHz mono WAVs with `soundcard`: default mic ("me") and WASAPI
  loopback of the default speaker ("others"). Pads silence so both tracks align to wall-clock time.
- `captions.py` `CaptionWatcher` thread polls the Teams window via UI Automation (`uiautomation`
  package) for the live-captions area and logs `(seconds, speaker, text)` observations.
  `dump_teams_tree()` writes the Teams UI tree to a file for tuning.
- `transcribe.py` faster-whisper on CPU, int8, VAD on. Model downloads to the data dir on first use.
- `merge.py` (pure, unit-tested): drops mic lines that are speaker bleed, names "others" segments by
  word overlap with caption observations in a time window, merges consecutive same-speaker lines,
  renders markdown.
- `session.py` one meeting: start/stop recorder + caption watcher, then `process()`.
- `app.py` pystray tray UI, monitor loop (every 2 s), worker queue for transcription.
- `probe.py` feasibility test exe: mic-app list, Teams detection, UI tree dump, 30 s recording,
  caption read. Report goes to `%LOCALAPPDATA%\MeetingNotes\probe_report.txt`.
- `tests/` pytest for merge and session processing (fake model). Run `python -m pytest -q tests`.
- `.github/workflows/build.yml` builds `MeetingNotes.zip` and `MeetingNotesTest.zip` on
  windows-latest and publishes a GitHub release on every push to main.

## Running from source on Windows

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pytest
python -m pytest -q tests
python run_probe.py     # feasibility test
python run_app.py       # tray app (logs to %LOCALAPPDATA%\MeetingNotes\meetnotes.log)
```

## Status (as of Nov 25, 2026)

Working on the work PC: app launches, manual "Record now" records, stop works, transcription
(small.en, model download succeeded) produces an accurate notes file.

Open issues, in priority order:
1. **Auto-start doesn't trigger.** `teams_call_active()` returned False during a real Teams call.
   Check the "apps using mic" lines in meetnotes.log to see the actual key names for new Teams
   (expected something like `MSTeams_8wekyb3d8bbwe`). Possibly LastUsedTimeStop isn't 0 while
   muted, or Teams' key name lacks "teams". Consider a fallback: an active Teams audio *render*
   session (pycaw/WASAPI session enumeration) or the Teams meeting window being present.
2. **Captions not found** although live captions were on. `find_caption_container()` looks for
   an element whose Name/AutomationId/ClassName contains "caption". Run `python run_probe.py`
   during a call with captions on and inspect `probe_output\teams_tree.txt` to find the real
   container and the speaker/text element structure, then update `find_caption_container` and
   `parse_entries`. New Teams is WebView2-based; the caption list may be deep in the tree, so
   `MAX_SEARCH_DEPTH` may need raising, or search by ControlType + structure instead of name.
3. Long single-speaker stretches render as one huge paragraph. Split lines in `build_transcript`
   when a merged line exceeds ~60 s or ~120 words.
4. "Length: 0 min" for calls under a minute. Show seconds for short calls.
5. uiautomation writes `@AutomationLog.txt` into the exe folder. Disable it
   (`uiautomation.Logger.SetLogFile('')`, or set the log path into the data dir).
6. Speaker diarization of the "others" track isn't implemented; unnamed speakers are "Other".
   If captions work, this may not be needed. If it is, prefer a lightweight ONNX diarizer
   (e.g. sherpa-onnx) over pyannote/torch to keep the package small.

## Rules

- Keep everything local and admin-free. Don't add cloud services or telemetry.
- Don't commit real meeting audio, transcripts, logs or `teams_tree.txt` files to the repo;
  they contain work content. `.gitignore` already excludes recordings, models, config and logs.
- After changing `merge.py`, run the tests.
