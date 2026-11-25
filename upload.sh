#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  CHINNU LEVEL PRO — GitHub upload (Termux)  v2
#
#  Usage:   bash upload.sh
#           bash upload.sh https://github.com/USER/REPO.git
#
#  Source folder (default):
#    /storage/emulated/0/bg/CHINNU_LEVEL_PRO
#
#  v2 fixes:
#   - "detected dubious ownership"  → safe.directory auto-add
#   - works from Termux home instead of shared storage (no FUSE issues)
#   - accepts "USER/REPO", "USER/REPO.git" or a full URL
#   - retries with pull --rebase when the remote is ahead
# ============================================================
set -u

SRC_DEFAULT="/storage/emulated/0/bg/CHINNU_LEVEL_PRO"
SRC="$SRC_DEFAULT"
REPO_ARG=""

for arg in "$@"; do
  case "$arg" in
    "")  continue ;;
    http://*|https://*|git@*|file://*)
        REPO_ARG="$arg" ;;
    /*|~/*)
        # absolute path — but only if it really is the project folder
        if [ -f "$arg/chinnu.py" ] || [ -f "$arg/index.html" ]; then
          SRC="$arg"
        else
          REPO_ARG="$arg"
        fi ;;
    *)
        if [ -d "$arg" ]; then
          SRC="$arg"                       # relative path that exists
        else
          REPO_ARG="$arg"                  # USER/REPO or REPO
        fi ;;
  esac
done

WORK="$HOME/CHINNU_LEVEL_PRO"

echo "════════════════════════════════════════"
echo " CHINNU LEVEL PRO → GitHub upload"
echo "════════════════════════════════════════"
echo

# ── 0. tools ─────────────────────────────────────────────────
if ! command -v git >/dev/null 2>&1; then
  echo "❌ git nahi hai →  pkg install git"; exit 1
fi
echo "✅ git $(git --version | awk '{print $3}')"

# ── 1. global git safety settings ────────────────────────────
#  Android shared storage is owned by a different uid, so git refuses
#  to operate there ("dubious ownership"). Whitelist everything.
git config --global --add safe.directory '*' 2>/dev/null || true
git config --global --add safe.directory "$SRC" 2>/dev/null || true
git config --global --add safe.directory "$WORK" 2>/dev/null || true
#  FUSE on /storage reports fake permission bits — ignore them
git config --global core.fileMode false 2>/dev/null || true

# ── 2. identity ──────────────────────────────────────────────
if ! git config --global user.name >/dev/null 2>&1 || [ -z "$(git config --global user.name)" ]; then
  read -r -p "GitHub username: " GN
  git config --global user.name "$GN"
fi
if ! git config --global user.email >/dev/null 2>&1 || [ -z "$(git config --global user.email)" ]; then
  read -r -p "GitHub email   : " GE
  git config --global user.email "$GE"
fi
echo "✅ identity: $(git config --global user.name) <$(git config --global user.email)>"

# ── 3. copy the project into Termux home ─────────────────────
#  Working directly on /storage/emulated/0 breaks git on many phones
#  (no chmod, no hardlinks, index.lock errors). Termux home is real ext4.
if [ -d "$SRC" ]; then
  echo "📦 copying from $SRC"
  mkdir -p "$WORK"
  # copy everything except git internals from the shared folder
  ( cd "$SRC" && tar -cf - --exclude='.git' . ) 2>/dev/null | ( cd "$WORK" && tar -xf - ) 2>/dev/null
  if [ $? -ne 0 ]; then
    cp -a "$SRC"/. "$WORK"/ 2>/dev/null || true
  fi
  echo "✅ working copy: $WORK"
elif [ -d "$WORK" ]; then
  echo "✅ working copy already at $WORK"
else
  echo "❌ Project folder nahi mila:"
  echo "   $SRC"
  echo "   aur $WORK bhi nahi hai."
  echo "   Pehle files wahan copy karo, ya chalao:"
  echo "     bash upload.sh /path/to/CHINNU_LEVEL_PRO"
  exit 1
fi

cd "$WORK" || { echo "❌ cd fail"; exit 1; }
rm -rf .git/index.lock 2>/dev/null || true

# ── 4. .gitignore + safe data files ──────────────────────────
cat > .gitignore <<'GITEOF'
__pycache__/
*.pyc
*.pyo
data/
*.log
.env
.DS_Store
Thumbs.db
GITEOF

[ -f accounts.json ]     || echo '[]' > accounts.json
[ -f orders.json ]       || echo '[]' > orders.json
[ -f redeem_codes.json ] || echo '[]' > redeem_codes.json
[ -f users.json ]        || echo '{}'  > users.json

if [ -s accounts.json ] && [ "$(tr -d '[:space:]' < accounts.json)" != "[]" ]; then
  echo
  echo "⚠️  accounts.json me asli UID/password ho sakte hain."
  read -r -p "   Public repo me nahi bhejna? [Y/n] " SK
  case "${SK:-Y}" in
    [Nn]*) echo "   → bhej rahe hain (zimmedari tumhari)";;
    *)     echo "accounts.json" >> .gitignore
           echo "   → skip kiya";;
  esac
fi

# ── 5. repo init ─────────────────────────────────────────────
NEW_REPO=0
if [ ! -d .git ]; then
  git init -q
  NEW_REPO=1
fi

# ── force the branch to be "main" (never master) ────────────
#  Old git defaults to master; that caused
#  "src refspec main does not match any" on push.
git symbolic-ref HEAD refs/heads/main 2>/dev/null || git checkout -q -B main 2>/dev/null || true

if [ -n "$(git rev-list -n1 --all 2>/dev/null)" ]; then
  # commits already exist — move the tip onto main no matter what it was called
  git branch -M main 2>/dev/null || true
fi

CUR_BRANCH="$(git symbolic-ref --short -q HEAD 2>/dev/null || echo main)"
if [ "$CUR_BRANCH" != "main" ]; then
  echo "⚠️  branch '$CUR_BRANCH' hai — 'main' banaya ja raha hai"
  git checkout -q -B main 2>/dev/null || true
  CUR_BRANCH="$(git symbolic-ref --short -q HEAD 2>/dev/null || echo main)"
fi
echo "✅ repo ready (branch: $CUR_BRANCH)"

# ── 6. remote ────────────────────────────────────────────────
normalize_url() {
  local u="$1"
  u="$(echo "$u" | tr -d '[:space:]')"
  case "$u" in
    "")                 echo ""; return;;
    file://*|git@*|https://*|http://*) ;;   # leave alone (file:// = tests/local)
    *github.com/*)      u="https://$u";;
    */*)                u="https://github.com/$u";;   # USER/REPO
    *)                  echo ""; return;;
  esac
  case "$u" in
    *.git) ;;
    *)     u="$u.git";;
  esac
  echo "$u"
}

CUR="$(git remote get-url origin 2>/dev/null || true)"
if [ -n "$REPO_ARG" ]; then
  NEWURL="$(normalize_url "$REPO_ARG")"
elif [ -n "$CUR" ]; then
  NEWURL=""
else
  echo
  echo "GitHub par naya repo banao:  https://github.com/new"
  echo "Format: USERNAME/REPO  ya  poora URL"
  echo
  read -r -p "Repo: " REPO_ARG
  NEWURL="$(normalize_url "$REPO_ARG")"
fi

if [ -n "${NEWURL:-}" ]; then
  if [ -z "$NEWURL" ]; then
    echo "❌ URL samajh nahi aaya. Example:"
    echo "   bash upload.sh chinnuvarsha5271-eng/Level"
    echo "   bash upload.sh https://github.com/chinuvarsha5271-eng/Level.git"
    exit 1
  fi
  if [ -n "$CUR" ]; then
    git remote set-url origin "$NEWURL"
  else
    git remote add origin "$NEWURL"
  fi
fi

FINAL="$(git remote get-url origin 2>/dev/null || true)"
if [ -z "$FINAL" ]; then
  echo "❌ koi remote set nahi hua"; exit 1
fi
echo "🔗 remote: $FINAL"
echo

# ── 7. commit ────────────────────────────────────────────────
git add -A
if git diff --cached --quiet; then
  echo "ℹ️  kuch naya nahi — commit pehle se hai"
  [ -n "$(git rev-list -n1 --all 2>/dev/null)" ] || git commit -q --allow-empty -m "init"
else
  git commit -q -m "CHINNU LEVEL PRO — $(date '+%d %b %Y %H:%M')"
  echo "✅ commit: $(git log -1 --pretty=%s)"
fi

# ── hard guarantee: something must exist on branch main ─────
if ! git rev-parse --verify -q main >/dev/null; then
  git checkout -q -B main 2>/dev/null || true
  git add -A
  git commit -q --allow-empty -m "init" 2>/dev/null || true
fi
if ! git rev-parse --verify -q main >/dev/null; then
  echo "❌ branch 'main' par koi commit nahi bana — kuch gadbad hai."
  echo "   Batao:  git status"
  exit 1
fi
echo "📌 branch main @ $(git rev-parse --short main) — $(git log -1 --pretty=%s main)"
echo

# ── 8. push (with one rebase retry) ──────────────────────────
do_push() {
  echo "⬆️  push ho raha hai…"
  git push -u origin main 2>&1 | tail -6
  return "${PIPESTATUS[0]}"
}

if do_push; then
  OK=1
else
  echo
  echo "↩️  remote aage hai — rebase karke dobara try…"
  if git pull --rebase origin main >/dev/null 2>&1 && do_push; then
    OK=1
  else
    OK=0
  fi
fi

echo
if [ "$OK" = "1" ]; then
  echo "════════════════════════════════════════"
  echo " ✅ UPLOAD HO GAYA"
  echo "════════════════════════════════════════"
  echo " Ab GitHub par:  Settings → Pages"
  echo "   Source : Deploy from a branch"
  echo "   Branch : main    Folder : / (root)"
  echo "   Save → 1–2 min → site live"
  echo
  echo " Kahin bhi file edit ki ho to dobara chalao:  bash upload.sh"
else
  echo "❌ Push fail. Ye check karo:"
  echo
  echo "  1) Repo GitHub par banaya hai? (khali repo hona chahiye)"
  echo "     $FINAL"
  echo "  2) Password ki jagah TOKEN daala?"
  echo "     github.com/settings/tokens → Generate new token (classic) → scope: repo"
  echo "  3) Username sahi hai? (email nahi — username)"
  echo
  echo "  Token yaad rakhne ke liye:"
  echo "     git config --global credential.helper store"
  echo
  echo "  Dobara try:  cd $WORK && git push -u origin main"
fi
