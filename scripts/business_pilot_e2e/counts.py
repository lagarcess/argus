"""Row counts for one owner on argus-biz-spaces, split Personal and Business. Prints no secrets."""
import json, sys
from pathlib import Path
import psycopg

env = {k: v.strip().strip('"') for k, v in (l.split("=", 1) for l in (Path(__file__).parent / "stack.env").read_text().splitlines() if "=" in l)}
assert ":57782/" in env["DB_URL"]
owner = sys.argv[1]
SPLIT = {
    "accounts": "select count(*) from public.financial_accounts where user_id=%s and {s}",
    "documents_live": "select count(*) from public.financial_source_connections where user_id=%s and source='statement' and status<>'disconnected' and {s}",
    "document_drafts": "select count(*) from public.financial_document_extractions d join public.financial_source_connections c on c.id=d.connection_id where d.user_id=%s and {s}",
    "import_events_open": "select count(*) from public.financial_import_events where user_id=%s and state='open' and {s}",
    "import_events_accepted": "select count(*) from public.financial_import_events where user_id=%s and state='accepted' and {s}",
}
SCOPES = {"personal": "owner_space_id is null", "business": "owner_space_id is not null"}
with psycopg.connect(env["DB_URL"]) as c:
    out = {}
    for scope, where in SCOPES.items():
        out[scope] = {}
        for name, sql in SPLIT.items():
            clause = where if name != "document_drafts" else "c." + where
            out[scope][name] = c.execute(sql.format(s=clause), (owner,)).fetchone()[0]
    rows = c.execute("select scope, count(distinct activity_id) from public.financial_activity_receipts where user_id=%s group by scope order by scope", (owner,)).fetchall()
    out["activities_by_receipt_scope"] = {str(k): v for k, v in rows}
    out["spaces"] = c.execute("select count(*) from public.spaces where created_by=%s and closed_at is null", (owner,)).fetchone()[0]
    out["storage_objects"] = c.execute("select count(*) from storage.objects where bucket_id='financial-document-sources' and starts_with(name, %s::text || '/')", (owner,)).fetchone()[0]
    out["whatsapp_messages_captured"] = c.execute("select count(*) from public.whatsapp_inbound_messages where destination_owner_id=%s and status='captured'", (owner,)).fetchone()[0]
    out["whatsapp_links_active"] = c.execute("select count(*) from public.whatsapp_sender_links where destination_owner_id=%s and status='active'", (owner,)).fetchone()[0]
print(json.dumps(out))
