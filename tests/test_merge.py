from datetime import datetime

from meetnotes.merge import assign_names, build_transcript, drop_bleed, to_markdown, OTHER


def seg(start, end, text):
    return {"start": start, "end": end, "text": text}


def test_names_matched_from_captions_with_lag():
    sys_segs = [
        seg(10, 14, "I think we should raise prices on storage by three percent"),
        seg(15, 18, "That seems low to me honestly"),
    ]
    obs = [
        (12, "Sarah Jones", "I think we should"),
        (16, "Sarah Jones", "I think we should raise prices on storage by 3 percent."),
        (20, "Mike Chen", "That seems low to me, honestly."),
    ]
    out = assign_names(sys_segs, obs)
    assert [s["speaker"] for s in out] == ["Sarah Jones", "Mike Chen"]


def test_unmatched_falls_back_to_neighbor_or_other():
    sys_segs = [
        seg(0, 3, "okay so the first item is the renewal list"),
        seg(4, 5, "um yeah"),
        seg(60, 62, "completely unrelated words here"),
    ]
    obs = [(2, "Sarah Jones", "Okay, so the first item is the renewal list.")]
    out = assign_names(sys_segs, obs)
    assert out[1]["speaker"] == "Sarah Jones"
    assert out[2]["speaker"] == OTHER


def test_bleed_removed():
    mic = [seg(10, 13, "raise prices on storage by three percent"), seg(30, 32, "sounds good to me")]
    sys_segs = [seg(10, 14, "I think we should raise prices on storage by three percent")]
    kept = drop_bleed(mic, sys_segs)
    assert [m["text"] for m in kept] == ["sounds good to me"]


def test_build_and_markdown():
    mic = [seg(5, 7, "Let's get started"), seg(7.5, 9, "first topic is pricing")]
    sys_segs = [seg(10, 12, "Sounds good")]
    obs = [(13, "Sarah Jones", "Sounds good.")]
    lines = build_transcript(mic, sys_segs, obs, my_name="Tom")
    assert len(lines) == 2
    assert lines[0]["speaker"] == "Tom" and "first topic" in lines[0]["text"]
    md = to_markdown(lines, datetime(2026, 11, 30, 9, 5), 1800, "Pricing sync")
    assert "# Pricing sync" in md and "Tom, Sarah Jones" in md and "[00:00:10] Sarah Jones" in md
