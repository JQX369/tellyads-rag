from io import StringIO

import csv

from tvads_rag import metadata_ingest


def _write_csv(tmp_path, rows):
    path = tmp_path / "meta.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "record_id",
                "movie_filename",
                "commercial_title",
                "advertiser-1",
                "views",
                "length",
            ]
        )
        writer.writerows(rows)
    return str(path)


def test_load_metadata_flags_hero_ads(tmp_path):
    path = _write_csv(
        tmp_path,
        [
            ["A1", "TA1", "Ad 1", "BrandA", "100", "30"],
            ["A2", "TA2", "Ad 2", "BrandB", "200", "30"],
            ["A3", "TA3", "Ad 3", "BrandC", "400", "30"],
            ["A4", "TA4", "Ad 4", "BrandD", "800", "30"],
            ["A5", "TA5", "Ad 5", "BrandE", "50", "30"],
            ["A6", "TA6", "Ad 6", "BrandF", "25", "30"],
            ["A7", "TA7", "Ad 7", "BrandG", "600", "30"],
            ["A8", "TA8", "Ad 8", "BrandH", "", "30"],
            ["A9", "TA9", "Ad 9", "BrandI", "0", "30"],
            ["A10", "TA10", "Ad 10", "BrandJ", "300", "30"],
        ],
    )

    index = metadata_ingest.load_metadata(path)

    # 10 rows => top 10% = top 1 ad (highest views = 800)
    assert index.hero_threshold == 800
    assert index.is_hero("A4")
    assert not index.is_hero("A3")

    entry = index.get("A3")
    assert entry is not None
    assert entry.title == "Ad 3"
    assert entry.views == 400
    assert entry.duration_seconds == 30









