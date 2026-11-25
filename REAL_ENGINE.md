# Real Garena Engine — how it works

## What changed
The panel no longer invents EXP. Every player card is now driven by a **real
Garena login** (protocol OB55).

```
UID + Password
   → OAuth guest token      (100067.connect.garena.com)
   → MajorLogin             (AES-128 + protobuf, loginbp.ppmainecoonghj.com)
   → GetLoginData           → nickname, level, total EXP, region, session keys
```

Files:
- `real_engine.py` — thin, documented bridge (the only file you need to read)
- `engine/` — the vendor protocol engine, unmodified (protobuf, AES, UDP)
- `chinnu.py` — panel: `/api/engine/status`, `/api/account/add`, `/api/account/bot`

## Modes
| Situation | Card shows | Numbers |
|---|---|---|
| engine present + login OK | `LIVE · GARENA` + `ONLINE` | real, read from Garena |
| engine present + login fails | `NOT CONNECTED` + red reason | nothing (dashes) |
| engine folder missing | `DEMO MODE` | simulated, clearly labelled |
| single `index.html` (GitHub Pages) | `DEMO MODE` | simulated, clearly labelled |

## Honest limits — read this
1. **This does not give free EXP.** EXP only comes from playing matches on
   Garena's servers. Nothing outside Garena can add EXP to an account.
2. A login is required, so **the operator holds the account password**. Automated
   logins on a third-party server are against Garena's terms and can get an
   account **banned**. Use only accounts you own and accept that risk.
3. Garena rate-limits aggressively. A busy datacenter IP returns
   `HTTP 429 error_too_many_requests`. Deploy on a clean IP and space out logins.
4. This build **logs in and reads the profile** — it does not join matches or
   farm EXP.

## Env
| Var | Meaning | Default |
|---|---|---|
| `PORT` | web port | `8080` |
| `FF_APP_VERSION` | pin the client version | auto (Play Store) |
| `LOGIN_CONCURRENCY` | parallel logins | engine default |
