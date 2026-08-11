from video_pipeline.server import parse_byte_range


def test_byte_ranges():
    assert parse_byte_range("bytes=10-19", 100) == (10, 19)
    assert parse_byte_range("bytes=90-", 100) == (90, 99)
    assert parse_byte_range("bytes=-10", 100) == (90, 99)
    assert parse_byte_range("bytes=120-130", 100) is None
