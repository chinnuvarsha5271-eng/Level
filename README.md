# CHINNU LEVEL PRO — Free Fire Level Up Panel

**Ek file = pura panel.** `chinnu.py` ke andar HTML + CSS + JS + API + storage sab hai.
Login / Create Account (username + password only) · Slots buying (list + validity) · Buy → seedha Telegram **@sbg_mod** · My IDs · Admin panel.

---

## ⚡ Local run

```bash
pip install aiohttp
python chinnu.py
# → http://localhost:8080
```

Admin login: username **`admin`** + password **`chinnu@5271`** (badalna ho: `ADMIN_PASSWORD (chinnu@5271)` env)

---

## 🚀 Railway deploy (2 min)

1. Repo me **`chinnu.py`**, **`Procfile`**, **`requirements.txt`** push karo
2. Railway → **New Project → Deploy from GitHub**
3. **Variables** (optional):
   | Key | Value |
   |---|---|
   | `ADMIN_PASSWORD (chinnu@5271)` | apna admin key (default `chinnu@5271`) |
   | `DATA_DIR` | `/data` (volume path) |
4. **Settings → Volumes** → mount **`/data`** ⚠️ (warna users/orders reset ho jayenge) + `DATA_DIR=/data` variable set karo
5. **Networking → Generate Domain** → live

`Procfile`: `web: python chinnu.py` — Railway ka `PORT` khud pick ho jata hai.

---

## 💳 Slots — list + time

## 🎟 Redeem Code System (admin only)

Code = **direct slot gift**. Admin code banaye → user panel e code daale → **turant slots + validity** add (koi payment nei).

Admin → **Redeem Codes** tab (sirf `chinnu` login):

| Field | Meaning |
|---|---|
| CODE | khali chhodo = auto `CHINNU-XXXXXX`, ya nijer code likho |
| SLOTS | kitna slot milega (min 1) |
| VALIDITY | hours (24 default, 48/72 bhi de sakte ho) |
| USES | 0 = unlimited users, 1 = single-use |
| LABEL | e.g. "Eid gift" |
| PREFIX | auto code ka prefix |

Controls per code: **Copy** · Disable/Enable · Reset (usage clear) · Delete.
Rules: ek user ek code ek bar; limit/expired/inactive/deleted → auto block; admin khud redeem nahi kar sakta.

User side: nav **Redeem** tab → code daalo → Redeem Now → slots + timer turant.
API: `POST /api/panel/redeem` (user) · `GET|POST /api/panel/admin/codes` (admin only) · data `redeem_codes.json`.

## Payment flow

Buy now → order create → **sidha `https://t.me/sbg_mod` chat khulbe** (order ID, plan, slots, amount, validity auto likha) → payment → admin approve → slots + 24h timer active.

| Plan | Slots | Price | Slot Validity | Per slot |
|---|---|---|---|---|

> **24 hour validity:** slot kena/milbar somoy theke thik 24 ghonta active. `expires_at` = now + 24h (top-up korle +24h extend). Expire hole `slots` auto 0 — abar slot kinte hobe. **Panel/account unlimited** (kokhono expire hoy na).

| TRIAL | 3 | ₹20 | **24 hours** | ₹6.7 |
| STARTER | 5 | ₹30 | **24 hours** | ₹6.0 |
| **POPULAR** ⭐ | 10 | ₹50 | **24 hours** | ₹5.0 |
| PRO | 25 | ₹100 | **24 hours** | ₹4.0 |
| BUSINESS | 50 | ₹180 | **24 hours** | ₹3.6 |

**1 slot = 1 ID.** ID delete korle slot abar free.

### Buy flow (jaisa aapne kaha)
```
Buy now dabao
   ↓
Confirm modal — plan, slots, validity, total, ORDER ID
   ↓
"Telegram e payment koro" → https://t.me/sbg_mod?text=...  (order ID + plan + amount auto likha)
   ↓
User payment screenshot Telegram pe pathay
   ↓
Admin panel → Orders → Approve → slots add (user dashboard e "Slots left" update)
```

---

## 🖥️ Pages (sab ek HTML me, SPA)

| Tab | Ki |
|---|---|
| Dashboard | stats (IDs / online / EXP / slots left) + accounts table |
| Buy Slots | 5 plans — price, validity, ₹/slot, instant activate |
| My IDs | apne accounts (level, EXP, matches, status) |
| Add ID | **single ID** (UID + password + name) — multi add nahi |
| How it works | 3 step guide |
| Admin | users slot control (+5 / set / delete) + orders approve/reject |

---

## 🔌 API

| Method | Path | Ki |
|---|---|---|
| POST | `/api/panel/register` | create account |
| POST | `/api/panel/login` | login (user / admin key) |
| GET | `/api/panel/me` | user + slots + left |
| POST | `/api/panel/order/create` | order banao → order ID |
| GET | `/api/panel/orders` | apne orders (admin: sob) |
| GET | `/api/panel/admin/users` | admin — user list |
| POST | `/api/panel/admin/user` | admin — add_slots / set_slots / delete |
| POST | `/api/panel/admin/order` | admin — approve / reject |
| GET | `/api/stats` | accounts (owner-scoped) |
| POST | `/api/account/add` | single ID add (slot check) |
| POST | `/api/account/delete` | ID delete (slot free) |

---

## 🔒 Security

- Password: **PBKDF2-SHA256**, 120k rounds + per-user salt (plain text nahi)
- Slot validity: 24 hours (`expires_at`, auto-expire) · Session cookie: HttpOnly, SameSite=Lax, 30 din, HMAC-signed
- User sirf apna data dekhta hai (owner-scoped), admin APIs pe `403`
- Slot bypass server-side blocked → `402 Slot shesh`
- Atomic file writes (`.tmp` + `os.replace`)

---

## 📁 Files

| File | Ki |
|---|---|
| `chinnu.py` | **poora panel** (HTML + API + storage) — bas ei file chalana hai |
| `page.html` | wahi HTML alag file me (edit karne ke liye aasan) |
| `Procfile`, `requirements.txt`, `nixpacks.toml` | Railway |
| `accounts.json` / `users.json` / `orders.json` | data (auto banti hain) |
| `screenshots/` | panel screenshots |

---

## ⚠️ Note

Ei panel sirf **account/slot management** karta hai — Free Fire bot `app.py` (previous build) me hai. Chaho to `chinnu.py` ke `api_account_add` se bot launch hook kar sakte ho (`accounts.json` same format, `uid` + `password`).
