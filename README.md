# Meeting Notes

A small Windows tray app that records Teams calls on your own PC, transcribes them locally,
labels who said what, and saves a `meeting_notes_YYYY-MM-DD_HHMM.md` file to a folder.
No bot joins the call, no admin rights are needed, and no audio leaves the PC.

## How it works

1. **Detects calls.** Windows tracks which apps are using the mic. When Teams starts using it,
   recording begins. When Teams lets go of it for 15 seconds, recording stops.
2. **Records two tracks.** Your microphone (you) and the PC's playback (everyone else), using
   Windows' built-in loopback capture.
3. **Reads live captions for names.** Teams live captions show only on your screen and label
   each line with the speaker. The app reads them through Windows accessibility (UI Automation).
4. **Transcribes locally** with faster-whisper on the CPU, then matches each line of the other
   people's audio to the caption speaker by words and timing.
5. **Writes the notes file** into `output_dir`, ready for your Claude task process.

## Step 1: run the feasibility test

1. Download `MeetingNotesTest.zip` from the latest release and unzip it anywhere in your user folder.
2. Start a Teams test call (Settings > Devices > Make a test call, or a meeting with only you)
   and turn on live captions (More > Language and speech > Show live captions).
3. Run `MeetingNotesTest.exe`. Talk during the 30 seconds.
4. When it finishes, `probe_report.txt` opens in Notepad. Share its results.

Only run the test on a call with no real work content. `probe_output\teams_tree.txt` lists
what's in your Teams window (chat names and so on), so read it before sharing and remove anything sensitive.

## Step 2: run the app

1. Download `MeetingNotes.zip`, unzip it to a folder in your user profile, and run `MeetingNotes.exe`.
   A blue notes icon appears in the system tray (it may be in the ^ overflow).
2. Right-click > Settings opens `config.json`. Settings, logs, recordings and the speech model live in
   `%LOCALAPPDATA%\MeetingNotes` so they never sync to OneDrive (Right-click > Open log folder).
   - `output_dir`: folder for notes. Set it to the folder your Claude process watches.
   - `my_name`: how you appear in transcripts.
   - `model`: `small.en` by default. Use `base.en` if it's too slow, or `medium.en` for more accuracy.
3. Restart the app after changing settings.
4. Optional: to start it at login, press Win+R, type `shell:startup`, and put a shortcut to `MeetingNotes.exe` there.

**First run:** the app downloads the speech model (about 250 MB for `small.en`) from Hugging Face
into the `models` folder. If your network blocks that, download the model on another machine
and copy the folder into `models`.

**Tray icon:** a red dot means recording, an amber dot means transcribing.

## Summaries and tasks

The app only writes transcripts. `CLAUDE_INSTRUCTIONS.md` (included in the zip) tells your work Claude
how to turn them into a summary, decisions and tasks. Set `my_name` to your name so it knows which lines are yours.

## Limits

- If live captions are off, other people show as "Other." You're always labeled correctly.
- If you use speakers instead of a headset, the app removes most of the echo of other people
  from your mic track, but a headset gives the cleanest result.
- A Teams update can change the caption layout. If names stop appearing, rerun the test and share `probe_output\teams_tree.txt` from the log folder.

## Building

Every push to `main` triggers GitHub Actions, which builds both zips on Windows and attaches
them to a release. Tests: `python -m pytest tests`.
