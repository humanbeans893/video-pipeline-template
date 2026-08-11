from video_pipeline.timeutil import (
    format_ass_time,
    format_clock,
    format_frame_timecode,
    parse_clock,
    split_caption,
)


def test_timecode_round_trip():
    value = 3723.456
    assert format_clock(value) == "01:02:03.456"
    assert parse_clock(format_clock(value)) == value
    assert format_frame_timecode(1.5, 30) == "00:00:01:15"
    assert format_ass_time(62.345) == "0:01:02.35"


def test_caption_split_prefers_punctuation():
    result = split_caption("最初の文です。次の文もあります。", limit=8)

    assert result == ["最初の文です。", "次の文もあります。"]
