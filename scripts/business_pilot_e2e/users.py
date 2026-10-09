"""Create owners A and B on the argus-biz-spaces stack via the local admin API. Prints no secrets."""
import json, secrets, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
stack = {k: v.strip().strip('"') for k, v in (l.split("=", 1) for l in (HERE / "stack.env").read_text().splitlines() if "=" in l)}
assert stack["API_URL"] == "http://127.0.0.1:57781", "argus-biz-spaces only"
admin = {"apikey": stack["SERVICE_ROLE_KEY"], "Authorization": f"Bearer {stack['SERVICE_ROLE_KEY']}", "Content-Type": "application/json"}
lines = []
for label in ("A", "B"):
    email = f"iso-owner-{label.lower()}-{sys.argv[1]}@qa.argus.local"
    password = secrets.token_urlsafe(18)
    body = {"email": email, "password": password, "email_confirm": True, "user_metadata": {"display_name": f"Owner {label}", "language": "en"}}
    request = urllib.request.Request(f"{stack['API_URL']}/auth/v1/admin/users", data=json.dumps(body).encode(), headers=admin)
    with urllib.request.urlopen(request) as response:
        user = json.loads(response.read())
        print(label, "admin create", response.status)
    lines += [f"OWNER_{label}_ID={user['id']}", f"OWNER_{label}_EMAIL={email}", f"OWNER_{label}_PASSWORD={password}"]
(HERE / "users.env").write_text("\n".join(lines) + "\n")
