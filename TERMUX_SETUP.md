# Termux se GitHub upload — CHINNU LEVEL PRO

Tumhara folder: `/storage/emulated/0/bg/CHINNU_LEVEL_PRO/`

---

## ⚡ FIX — jo error aaya uska seedha ilaaj

Do problems thi:

**1. `fatal: detected dubious ownership`**
Android ka `/storage/emulated/0` doosre user (uid) ka hai, isliye git us folder me
kaam karne se mana kar deta hai. Iska matlab ye **nahi** ki tum kuch galat kiye —
Android storage aisa hi hota hai.

**2. Repo URL adhoora tha**
Tumne `chinnuvarsha5271-eng/Level` daala — script ne usko folder samajh liya.
Poora URL chahiye: `https://github.com/chinnuvarsha5271-eng/Level.git`

### Ab ye 4 line chalao — bas

```bash
pkg install git -y
git config --global --add safe.directory '*'
git config --global core.fileMode false

cd /storage/emulated/0/bg/CHINNU_LEVEL_PRO
bash upload.sh https://github.com/chinnuvarsha5271-eng/Level.git
```

`upload.sh` ka naya version (v2) ye sab khud karta hai:
- `safe.directory` set karta hai
- project ko `~/CHINNU_LEVEL_PRO` me copy karta hai (Termux home = asli ext4,
  Android storage nahi — isliye git properly chalta hai)
- URL ko normalize karta hai (`USER/REPO` bhi chalega)
- push fail ho to `pull --rebase` karke ek baar dobara try karta hai

⚠️ **Naya `upload.sh` chahiye.** Purana wala delete karke naya daalo
(neeche Drive link hai).

### Token

Push par username daalne ke baad password ki jagah **token**:

1. [github.com/settings/tokens](https://github.com/settings/tokens)
2. **Generate new token (classic)** → Note: `termux` → Expiration: 90 days
3. Scope: ✅ **`repo`** → Generate → copy (`ghp_...`)
4. Push par password ki jagah wahi paste karo

Ek baar yaad rakhne ke liye:
```bash
git config --global credential.helper store
```

---

### 🔴 Naya error: `src refspec main does not match any`

Iska matlab: commit **`master`** branch pe gaya, tum **`main`** push kar rahe the.
Tumhare phone pe purana `upload.sh` chal raha tha (naya wala copy-step dikhata hai).

**Sabse fast fix — ye ek command:**

```bash
cd /storage/emulated/0/bg/CHINNU_LEVEL_PRO
bash ONE_LINE_FIX.sh
```

Ya manually (3 line, copy-paste):

```bash
cd /storage/emulated/0/bg/CHINNU_LEVEL_PRO
git branch -M main
git push -u origin main
```

`git branch -M main` = jo bhi branch hai usko **main** bana do.
Phir push me `main -> main` dikhega = ho gaya ✅

---

## Pehle ek baar — setup (2 minute)

```bash
pkg update && pkg install git -y
termux-setup-storage
```

`termux-setup-storage` chalane par phone me **"Allow"** ka popup aayega → Allow dabao.
Iske bina `/storage/emulated/0` folder padha nahi ja sakta.

Check karo folder dikh raha hai:

```bash
ls /storage/emulated/0/bg/CHINNU_LEVEL_PRO/
```

Agar files dikh gayi → aage badho. Agar `Permission denied` → `termux-setup-storage` dobara chalao.

---

## Tarika 1 — Script (sabse aasan)

**Step 1:** yeh 2 files phone me is folder me daal do:
`/storage/emulated/0/bg/CHINNU_LEVEL_PRO/`
- `upload.sh`
- `.gitignore`

Download karne ke liye Drive link neeche hai, ya file manager se copy kar do.

**Step 2:** GitHub par repo banao → [github.com/new](https://github.com/new)
- Name: `chinnu-level-pro`
- **Public** → Create

**Step 3:** Termux kholo aur chalao:

```bash
cd /storage/emulated/0/bg/CHINNU_LEVEL_PRO
bash upload.sh
```

Script khud poochhega:
- naam + email
- repo URL (jo copy kiya)
- username + **token** (password nahi — neeche dekho)

Bas. Upload ho jayega.

---

## Tarika 2 — Manual commands (copy-paste)

```bash
cd /storage/emulated/0/bg/CHINNU_LEVEL_PRO

# identity (ek baar)
git config --global user.name  "TERA_GITHUB_NAAM"
git config --global user.email "TERA_GITHUB_EMAIL"

# repo banao
git init
git branch -M main

# .gitignore — __pycache__ aur secrets push na ho
printf '%s\n' '__pycache__/' '*.pyc' 'data/' '*.log' '.env' > .gitignore

# sab add karo
git add -A
git commit -m "CHINNU LEVEL PRO"

# remote jodo
git remote add origin https://github.com/TERA_USERNAME/chinnu-level-pro.git

# push
git push -u origin main
```

Push karte waqt:
- **Username:** tumhara GitHub username
- **Password:** ❌ account password nahi chalega — **token** daalo (neeche)

---

## Token kaise banao (GitHub ne password hata diya hai)

1. Kholo → [github.com/settings/tokens](https://github.com/settings/tokens)
2. **Generate new token** → **Generate new token (classic)**
3. **Note:** `termux`
4. **Expiration:** 90 days (ya jitna chaho)
5. **Scopes:** ✅ `repo` (sirf yahi kaafi hai)
6. Neeche **Generate token**
7. Token copy karo (`ghp_...`) — **ek hi baar dikhta hai**, safe rakho

Push karte waqt password ki jagah wahi token paste karo.

Token yaad rakhne ke liye (optional):
```bash
git config --global credential.helper store
```
Pehli baar token daalne ke baad dobara nahi poochhega.

---

## Push ke baad — site live karo

1. Repo → **Settings**
2. Left sidebar → **Pages**
3. **Source:** `Deploy from a branch`
4. **Branch:** `main` · **Folder:** `/ (root)`
5. **Save**
6. 1–2 minute wait → link mil jayega:

```
https://TERA_USERNAME.github.io/chinnu-level-pro/
```

Termux me check bhi kar sakte ho:
```bash
curl -I https://TERA_USERNAME.github.io/chinnu-level-pro/
# HTTP/2 200  → chal gaya
```

---

## Token ko URL me daal ke push (agar prompt na aaye)

```bash
git remote set-url origin https://TOKEN@github.com/chinnuvarsha5271-eng/Level.git
git push -u origin main
```
⚠️ Token URL me hai — ye command kisi ko na bhejo, aur history me na rakho.

---

## Baad me update karna ho

```bash
cd /storage/emulated/0/bg/CHINNU_LEVEL_PRO
git add -A
git commit -m "update"
git push
```

Pages khud 1–2 min me naya version dikha dega.

---

## Common errors

| Error | Matlab | Fix |
|---|---|---|
| `Permission denied` / folder nahi mila | storage access band | `termux-setup-storage` |
| `remote origin already exists` | remote pehle se hai | `git remote set-url origin <URL>` |
| `Authentication failed` | password use kiya | token daalo (upar) |
| `src refspec main does not match` | branch ka naam `master` hai | `git branch -M main` phir push |
| `failed to push some refs` | GitHub pe pehle se commit hai | `git pull --rebase origin main` phir push |
| `Support for password authentication was removed` | wahi token wala issue | token banao |
| `detected dubious ownership` | Android storage doosre uid ka hai | `git config --global --add safe.directory '*'` |
| `index.lock: File exists` | purana lock pada hai | `rm -f .git/index.lock` |
| `remote: Not Found` | repo naam galat ya private+no token | URL check karo |
| `could not read Username` | non-interactive shell | token wale URL se push karo (neeche) |

---

## ⚠️ Zaroori — password wali file

`accounts.json` me asli UID/password ho sakte hain. **Public repo me kabhi na
daalo.** Script khud poochh lega. Manually kar rahe ho to:

```bash
echo "accounts.json" >> .gitignore
```

Server (Railway) par yeh file khud ban jayegi — koi dikkat nahi.

---

## Real engine (Railway) chahiye ho to

Pages par sirf `index.html` chalta hai (DEMO mode). Asli Garena login ke liye
`server/` folder alag repo me daalo:

```bash
mkdir -p ~/clp-server
cp -r /storage/emulated/0/bg/CHINNU_LEVEL_PRO/* ~/clp-server/
cd ~/clp-server
# jo files Railway ke liye hain sirf wahi rakho:
#   chinnu.py  real_engine.py  engine/  page.html
#   requirements.txt  Procfile  nixpacks.toml
#   accounts.json  orders.json  redeem_codes.json  users.json
rm -rf __pycache__
git init && git branch -M main && git add -A
git commit -m "server"
git remote add origin https://github.com/TERA_USERNAME/chinnu-level-pro-server.git
git push -u origin main
```

Phir [railway.app](https://railway.app) → New Project → Deploy from GitHub repo →
`chinnu-level-pro-server` → Settings → Networking → **Generate Domain**.
