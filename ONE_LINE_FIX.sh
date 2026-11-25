#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  EMERGENCY ONE-LINER — "src refspec main does not match any"
#  Chalao:
#    cd /storage/emulated/0/bg/CHINNU_LEVEL_PRO
#    bash ONE_LINE_FIX.sh
#
#  Ye kya karta hai:
#    - git ko Android storage pe chalne deta hai
#    - branch ka naam main kar deta hai (master → main)
#    - push karta hai
# ============================================================
set -u

REPO="https://github.com/chinnuvarsha5271-eng/Level.git"
DIR="/storage/emulated/0/bg/CHINNU_LEVEL_PRO"

echo "════════════════════════════════════════"
echo " FIX + PUSH"
echo "════════════════════════════════════════"

git config --global --add safe.directory '*'
git config --global core.fileMode false

cd "$DIR" || { echo "❌ $DIR nahi mila"; exit 1; }

if [ ! -d .git ]; then
  git init -q
fi

# branch ka naam pakka "main"
git symbolic-ref HEAD refs/heads/main 2>/dev/null || true
git rev-list -n1 --all >/dev/null 2>&1 && git branch -M main 2>/dev/null || true

# katai se main banao agar hai nahi
if ! git rev-parse --verify -q main >/dev/null; then
  git checkout -q -B main 2>/dev/null || true
fi

git add -A
if ! git rev-parse --verify -q main >/dev/null; then
  git commit -q --allow-empty -m "init"
else
  git diff --cached --quiet || git commit -q -m "CHINNU LEVEL PRO — $(date '+%d %b %Y %H:%M')"
fi

git remote remove origin 2>/dev/null || true
git remote add origin "$REPO"

echo
echo "branch : $(git symbolic-ref --short -q HEAD)"
echo "commit : $(git log -1 --pretty='%h %s' 2>/dev/null)"
echo "remote : $(git remote get-url origin)"
echo
echo "⬆️  push (username + TOKEN maangega)…"
git push -u origin main

echo
echo "Agar yahan 'main -> main' dikha to ho gaya ✅"
echo "Ab: GitHub → Settings → Pages → main / (root) → Save"
