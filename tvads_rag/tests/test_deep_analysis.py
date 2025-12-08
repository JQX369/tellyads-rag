from tvads_rag import deep_analysis


def test_normalise_hero_analysis_parses_valid_score():
    payload = {"overall_score": "87.5", "cinematography": {}}
    result = deep_analysis._normalise_hero_analysis(payload)
    assert result["overall_score"] == 87.5
    # ensure original payload not mutated
    assert payload["overall_score"] == "87.5"


def test_normalise_hero_analysis_handles_invalid_score():
    payload = {"overall_score": "not-a-number"}
    result = deep_analysis._normalise_hero_analysis(payload)
    assert result["overall_score"] is None


def test_normalise_hero_analysis_clamps_out_of_range():
    payload = {"overall_score": 200}
    result = deep_analysis._normalise_hero_analysis(payload)
    assert result["overall_score"] is None










