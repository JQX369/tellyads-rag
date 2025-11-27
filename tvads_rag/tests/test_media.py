from pathlib import Path

import pytest

from tvads_rag import media


def test_parse_frame_rate_fraction():
    fps = media._parse_frame_rate("30000/1001")
    assert pytest.approx(fps, rel=1e-4) == 29.97


def test_list_local_videos_filters_extensions(tmp_path):
    valid = tmp_path / "ad_one.mp4"
    valid.write_bytes(b"")
    (tmp_path / "notes.txt").write_text("ignore")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "ad_two.mov").write_bytes(b"")

    files = media.list_local_videos(str(tmp_path))
    resolved = {Path(f).name for f in files}
    assert resolved == {"ad_one.mp4", "ad_two.mov"}

