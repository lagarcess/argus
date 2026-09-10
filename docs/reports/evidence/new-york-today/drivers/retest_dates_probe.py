import json
from datetime import datetime

import pytest
from argus.api.chat.retest import complete_retest_turn, prepare_retest_turn
from argus.api.chat.confirmation import _format_confirmation_period
from argus.domain.market_data.capabilities import EASTERN

from tests.test_retest_action import (
    _CONVERSATION_ID, _SOURCE_RUN_ID, _USER_ID, _FakeRequest, _lifecycle_hooks,
    _retest_request, _valid_envelope, stored_run,  # noqa: F401
)


@pytest.mark.parametrize("at", [
    datetime(2026, 9, 9, 20, 17, tzinfo=EASTERN),
    datetime(2026, 9, 10, 12, 0, tzinfo=EASTERN),
], ids=["ny-evening-sep9", "ny-sep10-as-utc-host-read"])
@pytest.mark.parametrize("language", ["en", "es-419"])
def test_probe(stored_run, freeze_new_york_clock, at, language):
    freeze_new_york_clock(at)
    turn = prepare_retest_turn(
        payload=_retest_request(_valid_envelope(_SOURCE_RUN_ID)),
        request=_FakeRequest(), user_id=_USER_ID, conversation_id=_CONVERSATION_ID,
        language=language, confirmation_id=f"probe-{at:%H}-{language}",
    )
    final = complete_retest_turn(turn=turn, lifecycle_hooks=_lifecycle_hooks(),
                                 conversation_id=_CONVERSATION_ID, language=language)
    card = final["confirmation"]
    print("\nPROBE", at.isoformat(), language)
    print(" retest_period:", json.dumps(card.get("retest_period"), ensure_ascii=False))
    print(" date rows:", json.dumps([r for r in card.get("rows", []) if "date" in json.dumps(r).lower() or "period" in json.dumps(r).lower()], ensure_ascii=False))
    print(" launch date_range:", final["confirmation_payload"]["launch_payload"].get("date_range"))
    print(" constraints:", json.dumps(card.get("edit_constraints", {}).get("date_window")))
    print(" 12mo period:", _format_confirmation_period("past_12_months", language=language))
