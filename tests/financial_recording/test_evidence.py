from tests.financial_recording import scenarios


def test_committed_evidence_matches_the_model():
    assert scenarios.EVIDENCE.read_text(encoding="utf-8") == scenarios.render()
