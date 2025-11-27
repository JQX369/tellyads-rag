from tvads_rag import visual_analysis


def test_parse_storyboard_json_strips_wrapping():
    raw = "Gemini response:\n" + '[{"shot_index":0,"shot_label":"Opener"}]' + "\nThanks!"
    shots = visual_analysis._parse_storyboard_json(raw)  # type: ignore[attr-defined]
    assert shots[0]["shot_label"] == "Opener"


def test_normalise_shots_sets_defaults():
    raw_shots = [
        {
            "shot_index": 2,
            "description": "Product hero angle",
            "key_objects": "bottle",
        }
    ]
    cleaned = visual_analysis._normalise_shots(raw_shots)  # type: ignore[attr-defined]
    assert cleaned[0]["shot_index"] == 2
    assert cleaned[0]["key_objects"] == ["bottle"]

