from tvads_rag import analysis


def test_parse_with_retries_handles_wrapped_json():
    raw = "Some header\n" + '{"ad_metadata":{"brand_name":"Acme"},"segments":[],"chunks":[],"claims":[],"supers":[]}' + "\nFooter"
    parsed = analysis._parse_with_retries(raw)
    assert parsed["ad_metadata"]["brand_name"] == "Acme"


def test_normalise_analysis_fills_defaults():
    normalised = analysis._normalise_analysis({})
    assert normalised["ad_metadata"] == {}
    assert normalised["segments"] == []
    assert normalised["chunks"] == []
    assert normalised["claims"] == []
    assert normalised["supers"] == []

