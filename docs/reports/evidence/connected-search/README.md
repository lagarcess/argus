# Connected Search local iPhone demonstration

The [execution manifest](../../../specs/argus-execution-board.md#connected-search-on-iphone-lane)
owns scope, delivery status and remaining MVEE work. This demonstration uses
synthetic identities with real local Auth, API and Postgres. It does not verify
physical-iPhone internet delivery.

## Retained environment

Use `/Users/garces/.codex/worktrees/connected-search/private-alpha-next` on
`codex/connected-search`. The dedicated simulator is **Argus Connected Search**,
iPhone 17e with iOS 27, `01CBA853-5183-41AF-B1B8-024EF6DB8FFB`.
The installed bundle identifier is `local.argus.foundation`.

Search owns API 58800, Supabase 58801, Postgres 58802 and CAPTCHA bridge 58805.
Optional recovery acceptance uses proxy 58812. The ignored
`ios/.build/accounts-local-58800/client.json` contains local synthetic credentials.
Do not publish that file or raw authentication logs.

The physical-phone testing owner uses ports 58700–58749. This demonstration
never operates that environment. Existing 584xx, 585xx and 586xx demos are
preserved, along with their separate simulators and records.

## Restart while preserving records

Do not run `configure`, `seed`, `reset` or delete Docker volumes. Skip a service
command if that service already runs for this Search demo. In separate terminals:

```sh
cd /Users/garces/.codex/worktrees/connected-search/private-alpha-next
python3 ios/scripts/auth/local_stack.py start --accounts --port-base 58800
python3 ios/scripts/auth/local_stack.py api --accounts --port-base 58800 \
  --accounts-enabled on \
  --python /Users/garces/.codex/worktrees/5a42/private-alpha-next/.venv/bin/python
```

```sh
cd /Users/garces/.codex/worktrees/connected-search/private-alpha-next
python3 ios/scripts/auth/bridge.py --accounts --port-base 58800
```

Launch only the owned simulator:

```sh
xcrun simctl boot 01CBA853-5183-41AF-B1B8-024EF6DB8FFB # only if shut down
xcrun simctl launch 01CBA853-5183-41AF-B1B8-024EF6DB8FFB local.argus.foundation
open -a Simulator
```

## Verification record

Environment checkpoint at integration base `22f9c8cda`: the existing native
registered-session sign-in/relaunch/sign-out test passed on the new simulator
with clean Xcode exit zero. This verifies isolated setup, not connected Search.
Connected Search acceptance, recording and final review are pending implementation.
