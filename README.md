# CHINNU LEVEL PRO

Free Fire account panel — player cards with real Garena profile data.
Premium glass UI · English · mobile responsive · admin panel hidden from users.

![Players](screenshots/02-live-player.png)

---

## Two builds — pick the one you need

| | **A. GitHub Pages** (`index.html`) | **B. Server** (`server/`) |
|---|---|---|
| What it is | one HTML file, runs in the browser | Python app with the real Garena engine |
| Setup | upload 1 file, done | Railway / Render / VPS |
| Real Garena login | ❌ impossible (browsers can't open Garena sockets) | ✅ real OB55 login |
| Numbers on the card | simulated, labelled **DEMO MODE** | read from Garena, labelled **LIVE · GARENA** |
| Data | that browser only (`localStorage`) | shared JSON on the server |

**Browsers physically cannot talk to Garena's login servers.** If you want real
level / EXP on the cards you must run build **B**. Build A is a shareable demo.

---

## A. GitHub Pages (2 minutes)

1. **Create repo** → [github.com/new](https://github.com/new) → name it `chinnu-level-pro` → **Public** → Create
2. **Upload** → open `https://github.com/YOUR-USERNAME/chinnu-level-pro/upload/main`
3. Drag **`index.html`** (the filename must stay exactly `index.html`) → **Commit changes**
4. **Settings → Pages** → Source: `Deploy from a branch` → Branch `main`, folder `/ (root)` → **Save**
5. Wait 1–2 minutes. Your site:

```
https://YOUR-USERNAME.github.io/chinnu-level-pro/
```

Default login: `chinnu` / `chinnu@5271` (admin). Change it in the `CFG` block at
the top of `index.html`.

---

## B. Server build (real engine)

```
server/
├── chinnu.py          panel: web UI + API
├── real_engine.py     Garena bridge (documented, ~250 lines)
├── engine/            vendor protocol engine — protobuf, AES, OB55
├── page.html          UI source
├── requirements.txt
├── Procfile           web: python chinnu.py
└── REAL_ENGINE.md     how the engine works + its limits
```

### Railway (easiest)

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Upload the `server/` folder to a new repo first, then pick that repo
3. Railway reads `Procfile` automatically — no config needed
4. **Settings → Networking → Generate Domain** → open the URL

### Local

```bash
cd server
pip install -r requirements.txt
python chinnu.py          # http://localhost:8080
```

Check the engine is alive:

```bash
curl -H "Cookie: <your session>" http://localhost:8080/api/engine/status
# {"real": true, "mode": "real", "garena": {"release_version": "OB55", ...}}
```

---

## What the player card shows

```
ChinnuFF · UID 8496814458 · OB55 1.134.21        ● ONLINE
LIVE · GARENA

LEVEL          TOTAL EXP        LAST LOGIN      TARGET
72             36,48,738        2m ago          Lv 80
real account   read from        verified        [██░░] 0%
level          Garena

[ Re-login ]  [ Set Target ]  [ Delete ]
```

States the card can be in:

| Badge | Meaning | Numbers |
|---|---|---|
| `LIVE · GARENA` | logged in, profile read | real |
| `CONNECTING TO GARENA…` | login in flight | dashes |
| `NOT CONNECTED` | login failed — red reason shown | dashes |
| `DEMO MODE` | engine not deployed | simulated, labelled |

---

## Honest limits

1. **This does not add EXP.** EXP only comes from playing matches on Garena's
   servers. No outside panel can write EXP into an account.
2. The panel logs in with the account password, so the operator holds that
   password. Automated logins break Garena's terms and **can get an account
   banned**.
3. Garena blocks datacenter IPs — a busy host returns `HTTP 429
   error_too_many_requests`. Clean IP required, and space the logins out.
4. This build logs in and reads the profile. It does **not** join matches.

---

## Privacy

- Every user sees only their own IDs, slots, orders and expiry.
- Cross-user delete returns `404`, cross-user bot control returns `403`.
- The admin panel is invisible to normal users — no tab, no wording, no API.

## Plans (24h slots)

| Slots | Price |
|---|---|
| 3 | ₹20 |
| 5 | ₹30 |
| 10 | ₹50 |
| 25 | ₹100 |
| 50 | ₹180 |

Buy opens Telegram **@sbg_mod** directly with the order details.
