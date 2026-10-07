# WhatsApp webhook replay fixtures

Synthetic payloads in the shape of Meta's WhatsApp Cloud API `messages`
webhook. Numbers use the fictional 555 range, ids are made up, and no real
message, number or media id appears here. They prove code behavior only, not
connectivity to WhatsApp.

Tests sign each body with a test app secret and override `from`, `id` and the
text body where a case needs a different sender, message or link code.
