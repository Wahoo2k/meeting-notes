# Instructions for Claude: processing meeting_notes files

Paste this into your work Claude project's instructions, or save it as `CLAUDE.md` in the
folder your Claude task process reads. It tells Claude how to turn each transcript into a
summary and tasks.

---

## What you're receiving

Files named `meeting_notes_YYYY-MM-DD_HHMM.md` are automatic transcripts of Teams meetings.
Each has a short header (meeting title, date, start time, length, speakers) and then
timestamped lines: `**[HH:MM:SS] Speaker:** text`.

Read them with these limits in mind:
- The speaker labeled with my name (or "Me") is me, Tom. Those lines are always attributed correctly.
- Other speakers' names come from matching Teams captions and are usually right, but they can
  occasionally be swapped. "Other" means an unidentified speaker. If who said something matters
  (for example, who committed to a task) and the label is "Other" or looks inconsistent, say so
  instead of guessing.
- The text is machine transcription. Fix obvious mishearings from context (company names,
  product names, numbers), and flag any number, price or date you're unsure of.
- A "Note:" line in the header means something went wrong during recording (for example,
  captions were off). Mention it once at the top of your output.

## For each new file, produce

1. **Summary**: 3–6 bullets on what the meeting covered and why it mattered.
2. **Decisions**: what was agreed, with who agreed when it's clear.
3. **My action items**: tasks I own or committed to ("I'll...", "Tom will...", or assigned to
   me). For each: the task as a clear verb phrase, a due date if one was stated or clearly
   implied, and a short source quote with its timestamp.
4. **Others' action items**: what other people committed to, with owner and due date, so I
   can follow up.
5. **Open questions and follow-ups**: unresolved items, things to send, people to loop in.

Keep it tight. Skip small talk. Don't invent owners, dates or numbers that aren't in the transcript.

## Creating tasks

Create tasks only from "My action items". Use the task text as the title, include the
meeting title and date in the task notes, and set the due date when one was given. Don't
create tasks for other people's items; list them in the summary instead.

## Housekeeping

- Process each file once. After processing, move it to a `processed` subfolder (or record its
  name in `processed.txt`) so it isn't handled again.
- If a file is very short or has no real content (a test call, a dropped connection), note
  it in one line and skip task creation.
