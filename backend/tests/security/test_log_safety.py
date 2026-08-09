from __future__ import annotations

import json
import logging

from vaultlog.shared.logging import REDACTED_KEYS, redact_processor


def test_redact_processor_scrubs_dangerous_keys() -> None:
    canary = "SUPER-SECRET-CANARY"
    event = {
        "event": "debug",
        "password": canary,
        "nested": {"access_token": canary, "safe": "visible"},
        "items": [{"value": canary}],
    }
    scrubbed = redact_processor(logging.getLogger("test"), "info", event)
    rendered = json.dumps(scrubbed)
    assert canary not in rendered
    assert scrubbed["nested"]["safe"] == "visible"
    for key in REDACTED_KEYS:
        if key in event:
            assert scrubbed[key] == "[REDACTED]"
