# GitHub par upload kaise karein

Do cheezein upload kar sakte ho. **Jo chahiye wahi follow karo.**

---

# 🅰️ OPTION A — Live website (GitHub Pages)

Sabse fast. 1 file. 2 minute.

> Isme player card ke numbers **simulated** hain aur card pe **DEMO MODE** likha
> aata hai. Browser se Garena login possible nahi hota — isliye. Baaki poora
> panel (login, slots, redeem, admin, orders) 100% kaam karta hai.

## Step 1 — repo banao

1. Kholo → [github.com/new](https://github.com/new)
2. **Repository name:** `chinnu-level-pro`
3. **Public** select karo
4. **Create repository**

## Step 2 — file upload karo

1. Repo page pe **"uploading an existing file"** link click karo
   (ya seedha jao: `https://github.com/YOUR-USERNAME/chinnu-level-pro/upload/main`)
2. `index.html` drag-drop karo
   - ⚠️ Naam **bilkul** `index.html` hi rehna chahiye
   - Chaaho to `screenshots/` folder bhi upload kar do (README ke liye)
3. Neeche **Commit changes** dabao

## Step 3 — site chalu karo

1. Repo → **Settings** tab
2. Left sidebar → **Pages**
3. **Source:** `Deploy from a branch`
4. **Branch:** `main` · **Folder:** `/ (root)`
5. **Save** dabao

## Step 4 — wait karo

1–2 minute baad page refresh karo. Upar ek link dikhega:

```
https://YOUR-USERNAME.github.io/chinnu-level-pro/
```

Bas! Yeh link kisi ko bhi bhej sakte ho — Chrome me khulega, koi server nahi
chahiye. ✅

**Login:** `chinnu` / `chinnu@5271`

---

# 🅱️ OPTION B — Real engine wala server

Yeh build **asli Garena login** karta hai — level aur EXP account se padhta hai.
Railway/Render par chalta hai, GitHub Pages par **nahi** (Pages sirf static
files deta hai, Python nahi chalata).

## Step 1 — alag repo banao

1. [github.com/new](https://github.com/new)
2. Name: `chinnu-level-pro-server`
3. **Public** → **Create repository**

## Step 2 — `server/` folder ka content upload karo

1. Upload page kholo: `https://github.com/YOUR-USERNAME/chinnu-level-pro-server/upload/main`
2. `server/` folder ke **andar ki saari files** drag karo:
   ```
   chinnu.py
   real_engine.py
   engine/           ← poora folder, isme 7 files hain
   page.html
   requirements.txt
   Procfile
   nixpacks.toml
   REAL_ENGINE.md
   accounts.json  orders.json  redeem_codes.json  users.json
   ```
   ⚠️ `engine/` folder **zaroori** hai — uske bina real login nahi hoga
   (panel DEMO MODE me chala jayega)
3. **Commit changes**

> GitHub web upload folders support karta hai — `engine` folder ko drag karo,
> andar ki files khud chali jayengi. Agar dikkat aaye to GitHub Desktop ya
> `git push` use karo.

## Step 3 — Railway par deploy karo

1. [railway.app](https://railway.app) → GitHub se login
2. **New Project** → **Deploy from GitHub repo**
3. `chinnu-level-pro-server` select karo
4. Railway `Procfile` khud padh lega (`web: python chinnu.py`) — koi setting nahi chahiye
5. **Settings → Networking → Generate Domain**
6. Jo URL mile usko kholo

## Step 4 — check karo engine zinda hai

Browser me apne Railway URL par login karo, phir **My IDs** tab kholo.
Hero ke andar green bar dikhna chahiye:

```
● Real engine connected
  Live Garena protocol · Garena OB55 1.134.21
```

Green bar = real engine chal raha hai.
Orange bar = `Demo mode` — matlab `engine/` folder upload nahi hua.

## Step 5 — ID add karke test karo

1. **Add ID** tab → asli UID + password daalo → **Add ID & Start Bot**
2. Card pehle `CONNECTING TO GARENA…` dikhayega
3. ~15–30 sec me do me se ek hoga:

**Success:**
```
LIVE · GARENA   ● ONLINE
LEVEL 72   ·   TOTAL EXP 36,48,738   ·   LAST LOGIN 2m ago
```

**Fail (aur reason bhi dikhega):**
```
NOT CONNECTED  ● OFFLINE
Login failed. Garena rejected the login — wrong UID/password,
or this server IP is rate-limited
```

---

## Zaroori baatein ⚠️

| | |
|---|---|
| **EXP nahi milega** | EXP sirf Garena pe match khelne se aata hai. Koi bahar ka panel account me EXP nahi daal sakta. |
| **Password** | Panel password se asli login karta hai — matlab password tumhare server par store hota hai. Sirf apne accounts daalo. |
| **Ban risk** | Garena ke terms ke khilaf hai. Account ban ho sakta hai. |
| **429 error** | Garena datacenter IP block karta hai. Railway ka IP clean ho to chalega, warna nahi — card pe error dikhega. |

---

## Kaunsi file kahan

```
github/
├── index.html          → OPTION A: yeh ek file Pages par upload karo
├── README.md           → repo ka main page (optional)
├── GITHUB_UPLOAD_GUIDE.md  → yeh file
├── screenshots/        → README ke liye (optional)
└── server/             → OPTION B: iske andar ki files Railway repo me
    ├── chinnu.py
    ├── real_engine.py
    ├── engine/
    ├── requirements.txt
    └── Procfile
```

Dono ek hi repo me bhi rakh sakte ho — Pages root se `index.html` chalayega, aur
Railway me **Root Directory** `server` set kar dena.
