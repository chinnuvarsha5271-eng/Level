"""
CHINNU LEVEL PRO — single-file standalone panel
Everything in one file: HTML (login / create account / buy slots / my ids / admin), APIs, data storage.

Run:
    python chinnu.py            → http://0.0.0.0:8080
    PORT=8080 python chinnu.py

Env:
    ADMIN_KEY   admin password (hardcoded: chinnu@5271)
    DATA_DIR    users.json/orders.json/accounts.json folder (default: same folder)
"""
import os
import sys
import json
import time
import hmac
import hashlib
import secrets
import threading
from typing import Any, Dict, List, Optional

from aiohttp import web

# ───────────────────────────── config ─────────────────────────────
ADMIN_USER = "chinnu"
ADMIN_KEY = "chinnu@5271"
PORT = int(os.environ.get("PORT", "8080"))
HOST = "0.0.0.0"
BASE_DIR = os.environ.get("DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")
ORDERS_FILE = os.path.join(BASE_DIR, "orders.json")
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.json")
CODES_FILE = os.path.join(BASE_DIR, "redeem_codes.json")
TG_HANDLE = "sbg_mod"
SESSION_COOKIE = "clp_session"
SESSION_DAYS = 30
SECRET = hashlib.sha256(("chinnu-level-pro|" + ADMIN_KEY).encode()).digest()
LOCK = threading.RLock()

PLANS = {
    "p3":  {"slots": 3,  "price": 20,  "hours": 24, "name": "TRIAL"},
    "p5":  {"slots": 5,  "price": 30,  "hours": 24, "name": "STARTER"},
    "p10": {"slots": 10, "price": 50,  "hours": 24, "name": "POPULAR"},
    "p25": {"slots": 25, "price": 100, "hours": 24, "name": "PRO"},
    "p50": {"slots": 50, "price": 180, "hours": 24, "name": "BUSINESS"},
}

# ───────────────────────────── storage ─────────────────────────────
def _ensure():
    os.makedirs(BASE_DIR, exist_ok=True)
    for path, default in ((USERS_FILE, {"users": {}}),
                          (ORDERS_FILE, {"seq": 1, "orders": []}),
                          (ACCOUNTS_FILE, []),
                          (CODES_FILE, {"codes": {}})):
        if not os.path.exists(path):
            _write(path, default)


def _read(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if d is not None else default
    except Exception:
        return default


def _write(path: str, data: Any):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def users() -> Dict[str, Dict[str, Any]]:
    d = _read(USERS_FILE, {"users": {}})
    u = d.get("users") if isinstance(d, dict) else None
    return u if isinstance(u, dict) else {}


def save_users(u: Dict[str, Dict[str, Any]]):
    _write(USERS_FILE, {"users": u})


def orders() -> Dict[str, Any]:
    d = _read(ORDERS_FILE, {"seq": 1, "orders": []})
    if not isinstance(d, dict) or not isinstance(d.get("orders"), list):
        return {"seq": 1, "orders": []}
    d.setdefault("seq", 1)
    return d


def accounts() -> List[Dict[str, Any]]:
    d = _read(ACCOUNTS_FILE, [])
    return d if isinstance(d, list) else []


def codes() -> Dict[str, Dict[str, Any]]:
    d = _read(CODES_FILE, {"codes": {}})
    c = d.get("codes") if isinstance(d, dict) else None
    return c if isinstance(c, dict) else {}


def save_codes(c: Dict[str, Dict[str, Any]]):
    _write(CODES_FILE, {"codes": c})


def gen_code(prefix: str = "CHINNU") -> str:
    alpha = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    body = "".join(secrets.choice(alpha) for _ in range(6))
    return (prefix.strip().upper().replace(" ", "") or "CHINNU") + "-" + body[:3] + body[3:]


def redeem_check(code: str, username: str):
    """Validate a redeem code for a user. Returns (code_obj, error)."""
    code = str(code or "").strip().upper().replace(" ", "")
    if not code:
        return None, "Please enter a code"
    cs = codes()
    c = cs.get(code)
    if not c:
        return None, "Invalid code"
    if not c.get("active", True):
        return None, "This code is disabled"
    if c.get("expires_at") and int(c["expires_at"]) < int(time.time()):
        return None, "This code has expired"
    limit = int(c.get("limit", 0) or 0)
    if limit and int(c.get("used", 0) or 0) >= limit:
        return None, "This code has reached its usage limit"
    if username in set(c.get("redeemed_by") or []):
        return None, "You have already used this code"
    return c, ""


def hash_pw(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120_000).hex()


# ───────────────────────────── session ─────────────────────────────
def sign(p: str) -> str:
    return hmac.new(SECRET, p.encode(), hashlib.sha256).hexdigest()


def make_token(username: str, role: str) -> str:
    exp = str(int(time.time()) + SESSION_DAYS * 86400)
    payload = f"c|{username}|{role}|{exp}"
    return payload + "|" + sign(payload)


def read_token(tok: Optional[str]):
    if not tok:
        return None
    parts = tok.split("|")
    if len(parts) != 5 or parts[0] != "c":
        return None
    username, role, exp, sig = parts[1], parts[2], parts[3], parts[4]
    if not exp.isdigit() or int(exp) < time.time():
        return None
    if not hmac.compare_digest(sig, sign(f"c|{username}|{role}|{exp}")):
        return None
    return {"username": username, "role": role}


def current(request: web.Request):
    info = read_token(request.cookies.get(SESSION_COOKIE))
    if not info:
        return None
    if info["role"] != "admin" and info["username"] not in users():
        return None
    return info


def is_https(request: web.Request) -> bool:
    return request.secure or request.headers.get("X-Forwarded-Proto", "").lower() == "https"


def set_session(request: web.Request, resp: web.Response, username: str, role: str):
    resp.set_cookie(SESSION_COOKIE, make_token(username, role), max_age=SESSION_DAYS * 86400,
                    httponly=True, samesite="Lax", secure=is_https(request), path="/")


# ───────────────────────────── slot logic ─────────────────────────────
VALIDITY_HOURS = 24          # slot validity — 24 hours


def slots_of(username: str) -> Optional[int]:
    """Active slot count (0 once expired)."""
    u = users().get(username)
    if u is None:
        return None
    if u.get("expires_at") and int(u["expires_at"]) < time.time():
        return 0
    return int(u.get("slots", 0) or 0)


def slots_raw(username: str) -> Optional[int]:
    u = users().get(username)
    return None if u is None else int(u.get("slots", 0) or 0)


def expiry_of(username: str) -> Optional[int]:
    u = users().get(username) or {}
    ts = u.get("expires_at")
    return int(ts) if ts else None


def grant_slots(username: str, n: int, hours: int = 0) -> Optional[int]:
    """Add slots with 24h validity (extends if still active, else starts a new 24h window)."""
    hours = int(hours or 0) or VALIDITY_HOURS
    with LOCK:
        u = users()
        if username not in u:
            return None
        now = int(time.time())
        cur_exp = int(u[username].get("expires_at") or 0)
        if cur_exp > now:
            u[username]["expires_at"] = cur_exp + hours * 3600
        else:
            u[username]["expires_at"] = now + hours * 3600
        u[username]["slots"] = int(u[username].get("slots", 0) or 0) + int(n)
        u[username]["updated"] = now
        save_users(u)
        return u[username]["slots"]


def used_of(username: str) -> int:
    return sum(1 for a in accounts() if str(a.get("owner") or "") == username)


def left_of(username: str) -> Optional[int]:
    s = slots_of(username)
    return None if s is None else max(0, s - used_of(username))


# ───────────────────────────── API: auth ─────────────────────────────
async def api_register(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    username = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", ""))
    tg = str(data.get("telegram", "")).strip()
    if not (3 <= len(username) <= 24) or not all(c.isalnum() or c in "._-" for c in username):
        return web.json_response({"status": "error", "error": "Username must be 3-24 chars — letters, numbers, . _ - only"}, status=400)
    if len(password) < 4:
        return web.json_response({"status": "error", "error": "Password minimum 4 character"}, status=400)
    with LOCK:
        u = users()
        if username in u:
            return web.json_response({"status": "error", "error": "Username already exists"}, status=400)
        salt = secrets.token_hex(8)
        u[username] = {"username": username, "salt": salt, "password_hash": hash_pw(password, salt),
                       "slots": 0, "telegram": tg, "created": int(time.time()), "is_admin": False}
        save_users(u)
    resp = web.json_response({"status": "ok", "username": username, "role": "user", "slots": 0})
    set_session(request, resp, username, "user")
    print(f"[REGISTER] {username}")
    return resp


async def api_login(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not username or not password:
        return web.json_response({"status": "error", "error": "Please enter username and password"}, status=400)

    # admin login
    try:
        if hmac.compare_digest(password.encode(), ADMIN_KEY.encode()) and \
                username.lower() in (ADMIN_USER, "admin"):
            resp = web.json_response({"status": "ok", "username": "admin", "role": "admin", "admin": True})
            set_session(request, resp, "admin", "admin")
            return resp
    except Exception:
        pass

    u = users().get(username.lower())
    if not u or not hmac.compare_digest(hash_pw(password, str(u.get("salt", ""))), str(u.get("password_hash", ""))):
        return web.json_response({"status": "error", "error": "Wrong username or password"}, status=401)
    role = "admin" if u.get("is_admin") else "user"
    resp = web.json_response({"status": "ok", "username": u["username"], "role": role, "admin": role == "admin"})
    set_session(request, resp, u["username"], role)
    return resp


async def api_logout(request: web.Request):
    resp = web.json_response({"status": "ok"})
    resp.del_cookie(SESSION_COOKIE, path="/")
    return resp


async def api_me(request: web.Request):
    me = current(request)
    if not me:
        return web.json_response({"status": "error", "error": "unauthorized"}, status=401)
    uname, role = me["username"], me["role"]
    is_admin = role == "admin" or bool(users().get(uname, {}).get("is_admin"))
    return web.json_response({
        "status": "ok", "username": uname, "role": "admin" if is_admin else "user", "admin": is_admin,
        "slots": slots_of(uname), "used": used_of(uname) if slots_of(uname) is not None else None,
        "left": left_of(uname), "telegram": "@" + TG_HANDLE,
        "expires_at": expiry_of(uname), "validity_hours": VALIDITY_HOURS,
        "now": int(time.time()),
    })


# ───────────────────────────── API: orders ─────────────────────────────
async def api_order_create(request: web.Request):
    me = current(request)
    if not me:
        return web.json_response({"status": "error", "error": "unauthorized"}, status=401)
    try:
        data = await request.json()
    except Exception:
        data = {}
    plan = PLANS.get(str(data.get("plan", "")).strip())
    if not plan:
        return web.json_response({"status": "error", "error": "Please select a plan"}, status=400)
    with LOCK:
        d = orders()
        seq = int(d.get("seq", 1))
        order = {"id": "ORD" + str(seq).zfill(4), "username": me["username"], "plan": str(data["plan"]),
                 "slots": plan["slots"], "amount": plan["price"], "hours": plan["hours"],
                 "status": "pending_payment", "created": int(time.time()), "updated": int(time.time())}
        d["seq"] = seq + 1
        d["orders"].append(order)
        _write(ORDERS_FILE, d)
    print(f"[ORDER] {order['id']} {me['username']} {plan['slots']}slots ₹{plan['price']}")
    return web.json_response({"status": "ok", "order": order, "telegram": "@" + TG_HANDLE,
                              "telegram_url": "https://t.me/" + TG_HANDLE})


async def api_orders(request: web.Request):
    me = current(request)
    if not me:
        return web.json_response({"status": "error", "error": "unauthorized"}, status=401)
    d = orders()
    lst = d["orders"] if me["role"] == "admin" else [o for o in d["orders"] if o.get("username") == me["username"]]
    lst = sorted(lst, key=lambda o: o.get("created", 0), reverse=True)
    return web.json_response({"status": "ok", "orders": lst[:200]})


async def api_admin_user(request: web.Request):
    me = current(request)
    if not me or me["role"] != "admin":
        return web.json_response({"status": "error", "error": "Admin only"}, status=403)
    try:
        data = await request.json()
    except Exception:
        data = {}
    action = str(data.get("action", ""))
    uname = str(data.get("username", "")).strip()
    if action == "add_slots":
        n = int(data.get("slots", 0) or 0)
        total = grant_slots(uname, n)
        if total is None:
            return web.json_response({"status": "error", "error": "User not found"}, status=404)
        return web.json_response({"status": "ok", "username": uname, "slots": total,
                                  "expires_at": expiry_of(uname)})
    if action == "set_slots":
        n = max(0, int(data.get("slots", 0) or 0))
        with LOCK:
            u = users()
            if uname not in u:
                return web.json_response({"status": "error", "error": "User not found"}, status=404)
            u[uname]["slots"] = n
            if n > 0:
                u[uname]["expires_at"] = int(time.time()) + VALIDITY_HOURS * 3600
            save_users(u)
        return web.json_response({"status": "ok", "username": uname, "slots": n,
                                  "expires_at": expiry_of(uname)})
    if action == "delete":
        with LOCK:
            u = users()
            u.pop(uname, None)
            save_users(u)
        return web.json_response({"status": "ok", "deleted": uname})
    return web.json_response({"status": "error", "error": "Unknown action"}, status=400)


async def api_admin_users(request: web.Request):
    me = current(request)
    if not me or me["role"] != "admin":
        return web.json_response({"status": "error", "error": "Admin only"}, status=403)
    out = [{"username": k, "slots": slots_of(k) or 0, "used": used_of(k),
            "expires_at": expiry_of(k), "telegram": v.get("telegram", ""), "created": v.get("created", 0)}
           for k, v in users().items() if not v.get("is_admin")]
    out.sort(key=lambda x: x["created"], reverse=True)
    return web.json_response({"status": "ok", "users": out})


async def api_admin_order(request: web.Request):
    me = current(request)
    if not me or me["role"] != "admin":
        return web.json_response({"status": "error", "error": "Admin only"}, status=403)
    try:
        data = await request.json()
    except Exception:
        data = {}
    oid = str(data.get("order_id", ""))
    action = str(data.get("action", ""))
    with LOCK:
        d = orders()
        target = next((o for o in d["orders"] if o.get("id") == oid), None)
        if not target:
            return web.json_response({"status": "error", "error": "Order not found"}, status=404)
        if action == "approve":
            if target["status"] == "approved":
                return web.json_response({"status": "error", "error": "Already approved"}, status=400)
            n = int(data.get("slots") or target.get("slots") or 0)
            total = grant_slots(target["username"], n)
            if total is None:
                return web.json_response({"status": "error", "error": "User no longer exists (deleted)"}, status=404)
            target.update(status="approved", approved_slots=n, updated=int(time.time()))
            _write(ORDERS_FILE, d)
            print(f"[APPROVE] {oid} → {target['username']} +{n} slots (24h)")
            return web.json_response({"status": "ok", "order": target, "user_slots": total,
                                      "expires_at": expiry_of(target["username"])})
        if action in ("reject", "cancel"):
            target["status"] = "rejected" if action == "reject" else "cancelled"
            target["updated"] = int(time.time())
            _write(ORDERS_FILE, d)
            return web.json_response({"status": "ok", "order": target})
    return web.json_response({"status": "error", "error": "Unknown action"}, status=400)


# ───────────────────────────── API: redeem codes ─────────────────────────────
async def api_redeem(request: web.Request):
    """User redeems a code → slots credited instantly."""
    me = current(request)
    if not me:
        return web.json_response({"status": "error", "error": "unauthorized"}, status=401)
    if me["role"] == "admin":
        return web.json_response({"status": "error", "error": "Admin cannot redeem codes"}, status=403)
    try:
        data = await request.json()
    except Exception:
        data = {}
    code = str(data.get("code", "")).strip().upper().replace(" ", "")
    c, err = redeem_check(code, me["username"])
    if err:
        return web.json_response({"status": "error", "error": err}, status=400)
    slots = int(c.get("slots", 0) or 0)
    hours = int(c.get("hours", 0) or 0) or VALIDITY_HOURS
    with LOCK:
        cs = codes()
        rec = cs.get(code)
        if not rec:
            return web.json_response({"status": "error", "error": "Invalid code"}, status=400)
        rb = list(rec.get("redeemed_by") or [])
        if me["username"] in rb:
            return web.json_response({"status": "error", "error": "You have already used this code"}, status=400)
        total = grant_slots(me["username"], slots, hours)
        if total is None:
            return web.json_response({"status": "error", "error": "User not found"}, status=404)
        rb.append(me["username"])
        rec["redeemed_by"] = rb
        rec["used"] = int(rec.get("used", 0) or 0) + 1
        rec["last_used"] = int(time.time())
        save_codes(cs)
    print(f"[REDEEM] {code} → {me['username']} +{slots} slots / {hours}h")
    return web.json_response({"status": "ok", "code": code, "slots_added": slots, "hours": hours,
                              "user_slots": total, "expires_at": expiry_of(me["username"]),
                              "label": c.get("label") or ""})


async def api_admin_codes(request: web.Request):
    """Admin-only redeem-code manager. GET = list, POST = create/toggle/delete/reset."""
    me = current(request)
    if not me or me["role"] != "admin":
        return web.json_response({"status": "error", "error": "Admin only"}, status=403)
    if request.method == "GET":
        cs = codes()
        out = []
        for k, v in cs.items():
            out.append({"code": k, "slots": int(v.get("slots", 0) or 0),
                        "hours": int(v.get("hours", 0) or VALIDITY_HOURS),
                        "label": v.get("label", ""), "active": bool(v.get("active", True)),
                        "limit": int(v.get("limit", 0) or 0), "used": int(v.get("used", 0) or 0),
                        "expires_at": v.get("expires_at") or 0, "created": v.get("created", 0),
                        "redeemed_by": v.get("redeemed_by") or []})
        out.sort(key=lambda x: x["created"], reverse=True)
        return web.json_response({"status": "ok", "codes": out})

    try:
        data = await request.json()
    except Exception:
        data = {}
    action = str(data.get("action", "create")).strip()
    code = str(data.get("code", "")).strip().upper().replace(" ", "")
    with LOCK:
        cs = codes()
        if action == "create":
            if data.get("auto") or not code:
                code = gen_code(str(data.get("prefix", "CHINNU")))
                while code in cs:
                    code = gen_code(str(data.get("prefix", "CHINNU")))
            if len(code) < 3:
                return web.json_response({"status": "error", "error": "Code must be at least 3 characters"}, status=400)
            if code in cs:
                return web.json_response({"status": "error", "error": "This code already exists"}, status=400)
            try:
                slots = int(data.get("slots", 0) or 0)
                hours = int(data.get("hours", 0) or 0)
                limit = int(data.get("limit", 0) or 0)
            except Exception:
                return web.json_response({"status": "error", "error": "Please enter valid numbers"}, status=400)
            if slots < 1:
                return web.json_response({"status": "error", "error": "Minimum 1 slot"}, status=400)
            cs[code] = {"code": code, "slots": slots, "hours": hours or VALIDITY_HOURS,
                        "label": str(data.get("label", "") or "")[:40], "active": True,
                        "limit": max(0, limit), "used": 0, "redeemed_by": [],
                        "multi": bool(data.get("multi", False)),
                        "expires_at": 0, "created": int(time.time())}
            save_codes(cs)
            print(f"[CODE] new {code} +{slots} slots / {hours or VALIDITY_HOURS}h")
            return web.json_response({"status": "ok", "code_obj": cs[code]})
        if not code or code not in cs:
            return web.json_response({"status": "error", "error": "Code not found"}, status=404)
        if action == "toggle":
            cs[code]["active"] = not bool(cs[code].get("active", True))
            save_codes(cs)
            return web.json_response({"status": "ok", "code_obj": cs[code]})
        if action == "delete":
            cs.pop(code, None)
            save_codes(cs)
            return web.json_response({"status": "ok", "deleted": code})
        if action == "reset":
            cs[code]["used"] = 0
            cs[code]["redeemed_by"] = []
            save_codes(cs)
            return web.json_response({"status": "ok", "code_obj": cs[code]})
    return web.json_response({"status": "error", "error": "Unknown action"}, status=400)


# ───────────────────────────── API: accounts ─────────────────────────────
async def api_stats(request: web.Request):
    me = current(request)
    if not me:
        return web.json_response({"status": "error", "error": "unauthorized"}, status=401)
    accs = accounts()
    if me["role"] != "admin":
        accs = [a for a in accs if str(a.get("owner") or "") == me["username"]]
    out = []
    for a in accs:
        out.append({
            "uid": a.get("uid"), "nickname": a.get("name") or ("Player_" + str(a.get("uid"))[:6]),
            "level": int(a.get("level", 1) or 1), "gained_exp": int(a.get("gained_exp", 0) or 0),
            "matches_played": int(a.get("matches_played", 0) or 0),
            "status": a.get("status", "CONNECTING"), "region": a.get("region", "BD"),
        })
    return web.json_response({"status": "ok", "accounts": out,
                              "total_accounts": len(out),
                              "total_gained_exp": sum(x["gained_exp"] for x in out),
                              "role": me["role"]})


async def api_account_add(request: web.Request):
    me = current(request)
    if not me:
        return web.json_response({"status": "error", "error": "unauthorized"}, status=401)
    try:
        data = await request.json()
    except Exception:
        data = {}
    uid = str(data.get("uid", "")).strip()
    pwd = str(data.get("password", "")).strip()
    name = str(data.get("name", "")).strip()
    if not uid or not pwd:
        return web.json_response({"status": "error", "error": "Both UID and password are required"}, status=400)
    with LOCK:
        accs = accounts()
        already = next((a for a in accs if str(a.get("uid")) == uid), None)
        if already is not None:
            if me["role"] != "admin" and str(already.get("owner") or "") != me["username"]:
                return web.json_response({"status": "error", "error": "This ID is already added"}, status=400)
        else:
            if me["role"] != "admin":
                left = left_of(me["username"])
                if left is not None and left < 1:
                    return web.json_response({"status": "error",
                                              "error": "No slots left or expired — buy new slots",
                                              "slots_left": 0}, status=402)
        accs = [a for a in accs if str(a.get("uid")) != uid]
        accs.append({"uid": uid, "password": pwd, **({"name": name} if name else {}),
                     "owner": me["username"], "region": str(data.get("region") or "BD"),
                     "status": "CONNECTING", "level": 1, "gained_exp": 0, "matches_played": 0,
                     "added": int(time.time())})
        _write(ACCOUNTS_FILE, accs)
    return web.json_response({"status": "ok", "uid": uid, "slots_left": left_of(me["username"])})


async def api_account_delete(request: web.Request):
    me = current(request)
    if not me:
        return web.json_response({"status": "error", "error": "unauthorized"}, status=401)
    try:
        data = await request.json()
    except Exception:
        data = {}
    uid = str(data.get("uid", "")).strip()
    with LOCK:
        accs = accounts()
        keep, removed = [], None
        for a in accs:
            if str(a.get("uid")) == uid and (me["role"] == "admin" or str(a.get("owner") or "") == me["username"]):
                removed = a
            else:
                keep.append(a)
        if removed is None:
            return web.json_response({"status": "error", "error": "ID not found"}, status=404)
        _write(ACCOUNTS_FILE, keep)
    return web.json_response({"status": "ok", "deleted": uid, "slots_left": left_of(me["username"])})


# ───────────────────────────── pages ─────────────────────────────
PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#05070d">
<title>CHINNU LEVEL PRO — Free Fire Level Up</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#04060b; --card:#0b1120; --card2:#0e1526;
  --line:rgba(122,142,180,.14); --line2:rgba(122,142,180,.26);
  --txt:#eef3fc; --mut:#78859f; --mut2:#5b6780;
  --gr:#00f0a8; --gr2:#00c98f; --bl:#2ea8ff; --vi:#a06cff; --am:#ffb020; --rd:#ff4d6d;
  --grad:linear-gradient(135deg,#00f0a8,#2ea8ff);
  --gradv:linear-gradient(135deg,#a06cff,#2ea8ff);
  --gradg:linear-gradient(135deg,#00f0a8,#00c98f);
  --r:20px;
}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--txt);font-family:'Inter','Segoe UI',system-ui,-apple-system,Roboto,sans-serif;
  font-size:14px;-webkit-font-smoothing:antialiased;overflow-x:hidden;min-height:100vh}

/* ══════ ambient bg ══════ */
.amb{position:fixed;inset:0;z-index:-2;overflow:hidden;pointer-events:none}
.blob{position:absolute;border-radius:50%;filter:blur(60px);opacity:.5}
.b1{width:58vw;height:58vw;left:-16vw;top:-22vw;background:radial-gradient(circle,rgba(0,240,168,.5),transparent 67%);
  animation:fl 22s ease-in-out infinite alternate}
.b2{width:52vw;height:52vw;right:-16vw;top:-8vw;background:radial-gradient(circle,rgba(46,168,255,.45),transparent 67%);
  animation:fl 26s ease-in-out infinite alternate-reverse}
.b3{width:46vw;height:46vw;left:26vw;bottom:-24vw;background:radial-gradient(circle,rgba(160,108,255,.38),transparent 67%);
  animation:fl 30s ease-in-out infinite alternate}
@keyframes fl{from{transform:translate3d(0,0,0) scale(1)}to{transform:translate3d(3vw,3vw,0) scale(1.16)}}
.grid-ov{position:absolute;inset:0;
  background-image:linear-gradient(rgba(255,255,255,.032) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.032) 1px,transparent 1px);
  background-size:56px 56px;
  mask-image:radial-gradient(ellipse 90% 70% at 50% 0%,#000 10%,transparent 80%);
  -webkit-mask-image:radial-gradient(ellipse 90% 70% at 50% 0%,#000 10%,transparent 80%)}
.vig{position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(ellipse at 50% 0%,transparent 40%,rgba(0,0,0,.55) 100%)}

/* ══════ shell ══════ */
.wrap{max-width:1200px;margin:0 auto;padding:20px 20px 70px}
.top{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:24px}
.brand{display:flex;align-items:center;gap:12px;min-width:0}
.mark{width:44px;height:44px;border-radius:14px;background:var(--gradg);display:grid;place-items:center;flex:0 0 44px;
  box-shadow:0 8px 26px rgba(0,240,168,.4),inset 0 1px 0 rgba(255,255,255,.4);position:relative}
.mark::after{content:'';position:absolute;inset:0;border-radius:14px;box-shadow:0 0 0 1px rgba(255,255,255,.18) inset}
.mark svg{width:24px;height:24px}
.brand h1{font-size:17.5px;font-weight:850;letter-spacing:.2px;line-height:1.15;white-space:nowrap}
.brand h1 b{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.brand small{display:block;color:var(--mut2);font-size:9.5px;letter-spacing:2.4px;font-weight:800;margin-top:3px}
.hdr-r{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.chip{display:inline-flex;align-items:center;gap:8px;height:36px;padding:0 13px;border-radius:11px;
  background:rgba(255,255,255,.045);border:1px solid var(--line);font-size:12px;color:#b5c0d4;
  backdrop-filter:blur(12px);white-space:nowrap}
.chip b{color:#fff;font-weight:800}
.chip.slot{border-color:rgba(0,240,168,.32);background:rgba(0,240,168,.09);color:#9df7d3}
.chip.slot b{color:#00f0a8}
.dot-live{width:7px;height:7px;border-radius:50%;background:var(--gr);box-shadow:0 0 9px var(--gr);animation:pl 2s infinite}
@keyframes pl{50%{opacity:.3;transform:scale(.8)}}
.avatar{width:36px;height:36px;border-radius:11px;background:linear-gradient(135deg,#1f2b45,#131c2e);
  border:1px solid var(--line2);display:grid;place-items:center;font-weight:850;font-size:13px;
  color:#9df7d3;text-transform:uppercase;flex:0 0 36px}

/* ══════ buttons ══════ */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:42px;padding:0 18px;
  border-radius:12px;font:inherit;font-weight:800;font-size:13.5px;cursor:pointer;transition:.18s;
  background:rgba(255,255,255,.055);color:var(--txt);border:1px solid var(--line2);white-space:nowrap}
.btn:hover{background:rgba(255,255,255,.1);transform:translateY(-1px);border-color:rgba(122,142,180,.4)}
.btn:active{transform:translateY(0)}
.btn.pri{background:var(--gradg);color:#001b12;border:0;box-shadow:0 10px 28px rgba(0,240,168,.3),inset 0 1px 0 rgba(255,255,255,.3)}
.btn.pri:hover{box-shadow:0 14px 36px rgba(0,240,168,.45)}
.btn.blu{background:linear-gradient(135deg,#2ea8ff,#1e7fd4);color:#fff;border:0;box-shadow:0 10px 26px rgba(46,168,255,.3)}
.btn.tg{background:linear-gradient(135deg,#2AABEE,#229ED9);color:#fff;border:0;box-shadow:0 10px 26px rgba(42,171,238,.34)}
.btn.dan{background:rgba(255,77,109,.1);border:1px solid rgba(255,77,109,.34);color:#ff9aab}
.btn.dan:hover{background:rgba(255,77,109,.18)}
.btn.sm{height:33px;padding:0 12px;font-size:12px;border-radius:9px}
.btn.xs{height:28px;padding:0 9px;font-size:11px;border-radius:8px;font-weight:800}
.btn.blk{width:100%}
.btn:disabled{opacity:.5;cursor:not-allowed;transform:none;box-shadow:none}

/* ══════ glass card ══════ */
.glass{background:linear-gradient(168deg,rgba(17,24,40,.78),rgba(9,14,24,.86));
  border:1px solid var(--line);border-radius:var(--r);
  backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  box-shadow:0 22px 60px rgba(0,0,0,.5),inset 0 1px 0 rgba(255,255,255,.045)}

/* ══════ auth ══════ */
.auth-wrap{min-height:calc(100vh - 120px);display:grid;place-items:center;padding:10px 0 30px}
.auth{width:100%;max-width:424px;padding:30px 28px;position:relative;overflow:hidden}
.auth::before{content:'';position:absolute;top:0;left:18%;right:18%;height:2px;
  background:var(--grad);border-radius:0 0 4px 4px;box-shadow:0 0 20px rgba(0,240,168,.7)}
.auth::after{content:'';position:absolute;top:-90px;right:-70px;width:230px;height:230px;border-radius:50%;
  background:radial-gradient(circle,rgba(46,168,255,.2),transparent 68%);pointer-events:none}
.auth .kicker{display:inline-flex;align-items:center;gap:7px;font-size:10px;letter-spacing:2px;font-weight:850;
  color:#9df7d3;background:rgba(0,240,168,.1);border:1px solid rgba(0,240,168,.3);padding:5px 11px;border-radius:20px;margin-bottom:15px}
.auth h2{font-size:23px;font-weight:850;letter-spacing:-.4px}
.auth .sub{color:var(--mut);font-size:12.5px;margin:7px 0 22px;line-height:1.65}
.seg{display:flex;gap:4px;background:rgba(0,0,0,.35);border:1px solid var(--line);border-radius:13px;padding:4px;margin-bottom:20px}
.seg button{flex:1;height:38px;background:none;border:1px solid transparent;color:var(--mut);font:inherit;
  font-size:13px;font-weight:800;border-radius:10px;cursor:pointer;transition:.18s}
.seg button:hover{color:#cfd8e8}
.seg button.on{background:linear-gradient(135deg,rgba(0,240,168,.2),rgba(46,168,255,.16));color:#fff;
  border-color:rgba(0,240,168,.42);box-shadow:0 6px 18px rgba(0,240,168,.14)}
label{display:block;font-size:9.5px;letter-spacing:1.4px;color:var(--mut);font-weight:850;margin:0 0 8px}
label i{font-style:normal;color:var(--mut2);letter-spacing:.4px;font-weight:700;text-transform:none}
.inp{width:100%;height:46px;background:rgba(2,5,10,.72);border:1px solid var(--line2);border-radius:12px;
  padding:0 15px;color:var(--txt);font:inherit;font-size:14px;outline:none;transition:.16s}
.inp::placeholder{color:#4c566b}
.inp:focus{border-color:rgba(0,240,168,.6);background:rgba(2,5,10,.95);box-shadow:0 0 0 3px rgba(0,240,168,.13)}
.fld{margin-bottom:15px}
.msg{margin-top:14px;font-size:12.5px;padding:11px 14px;border-radius:11px;display:none;line-height:1.55}
.msg.err{display:block;background:rgba(255,77,109,.1);border:1px solid rgba(255,77,109,.36);color:#ff9aab}
.msg.ok{display:block;background:rgba(0,240,168,.1);border:1px solid rgba(0,240,168,.36);color:#8bf7d0}
.auth .foot{margin-top:20px;padding-top:17px;border-top:1px solid var(--line);text-align:center;
  font-size:11.5px;color:var(--mut);line-height:1.9}
.auth .foot a{color:#5edcff;font-weight:750;text-decoration:none;display:inline-flex;align-items:center;gap:5px}
.auth .foot a:hover{text-decoration:underline}

/* ══════ tabs ══════ */
.tabs{display:flex;gap:5px;padding:5px;border-radius:15px;background:rgba(255,255,255,.035);
  border:1px solid var(--line);margin-bottom:22px;overflow:auto;scrollbar-width:none;backdrop-filter:blur(12px)}
.tabs::-webkit-scrollbar{display:none}
.tabs button{display:flex;align-items:center;gap:8px;height:40px;padding:0 15px;background:none;
  border:1px solid transparent;color:#93a0b8;font:inherit;font-size:12.5px;font-weight:800;border-radius:11px;
  cursor:pointer;white-space:nowrap;transition:.16s}
.tabs button:hover{color:#fff;background:rgba(255,255,255,.05)}
.tabs button.on{background:linear-gradient(135deg,rgba(0,240,168,.18),rgba(46,168,255,.14));
  border-color:rgba(0,240,168,.4);color:#fff;box-shadow:0 4px 16px rgba(0,240,168,.15)}
.tabs svg{width:15px;height:15px;flex:0 0 15px}
.tabs .cnt{background:rgba(0,240,168,.2);color:#9df7d3;font-size:10px;font-weight:900;padding:1px 6px;border-radius:20px}

/* ══════ views ══════ */
.view{display:none}.view.on{display:block;animation:up .34s cubic-bezier(.2,.9,.3,1)}
@keyframes up{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}

/* hero */
.hero{position:relative;overflow:hidden;padding:28px 28px 26px;margin-bottom:18px}
.hero::before{content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 70% 120% at 88% 0%,rgba(0,240,168,.15),transparent 62%),
             radial-gradient(ellipse 60% 100% at 0% 100%,rgba(160,108,255,.13),transparent 62%)}
.hero::after{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--grad);box-shadow:0 0 18px rgba(0,240,168,.8)}
.hero>*{position:relative}
.hero .badge24{display:inline-flex;align-items:center;gap:7px;font-size:9.5px;font-weight:900;letter-spacing:1.6px;
  color:#001b12;background:var(--gradg);padding:5px 12px;border-radius:20px;margin-bottom:13px;
  box-shadow:0 6px 18px rgba(0,240,168,.32)}
.hero h2{font-size:27px;font-weight:850;letter-spacing:-.7px;line-height:1.15}
.hero h2 em{font-style:normal;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{color:#93a0b8;font-size:13px;margin-top:9px;max-width:600px;line-height:1.7}
.hero .row{display:flex;gap:10px;margin-top:20px;flex-wrap:wrap}
.hero .timer{margin-top:16px;display:inline-flex;align-items:center;gap:9px;font-size:12px;color:#9df7d3;
  background:rgba(0,240,168,.09);border:1px solid rgba(0,240,168,.28);padding:8px 14px;border-radius:11px}
.hero .timer svg{width:14px;height:14px}
.hero .timer b{font-family:ui-monospace,Menlo,monospace;letter-spacing:.5px;color:#fff}

/* stats */
.stats{display:grid;gap:13px;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));margin-bottom:22px}
.stat{position:relative;overflow:hidden;padding:17px 18px;border-radius:17px;
  background:linear-gradient(165deg,rgba(20,28,46,.8),rgba(9,14,24,.9));border:1px solid var(--line)}
.stat::before{content:'';position:absolute;right:-26px;top:-26px;width:88px;height:88px;border-radius:50%;opacity:.5}
.stat.g::before{background:radial-gradient(circle,rgba(0,240,168,.34),transparent 68%)}
.stat.b::before{background:radial-gradient(circle,rgba(46,168,255,.34),transparent 68%)}
.stat.v::before{background:radial-gradient(circle,rgba(160,108,255,.34),transparent 68%)}
.stat.a::before{background:radial-gradient(circle,rgba(255,176,32,.3),transparent 68%)}
.stat .ic{position:absolute;right:15px;top:15px;width:17px;height:17px;opacity:.55}
.stat .k{font-size:9px;letter-spacing:1.7px;color:var(--mut);font-weight:900;position:relative}
.stat .v{font-size:29px;font-weight:850;letter-spacing:-1px;margin-top:9px;line-height:1;position:relative}
.stat .v small{font-size:11.5px;color:var(--mut);font-weight:750;letter-spacing:0}
.stat .b{height:3px;border-radius:3px;background:rgba(255,255,255,.08);margin-top:13px;overflow:hidden;position:relative}
.stat .b i{display:block;height:100%;border-radius:3px;background:var(--grad);transition:width .5s}
.stat.g .v{color:var(--gr)}.stat.b .v{color:var(--bl)}.stat.v .v{color:#b98cff}.stat.a .v{color:var(--am)}

/* section head */
.sh{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:26px 0 14px;flex-wrap:wrap}
.sh h3{font-size:11px;letter-spacing:2.2px;color:#8b98b1;font-weight:900;display:flex;align-items:center;gap:9px}
.sh h3::before{content:'';width:3px;height:13px;border-radius:2px;background:var(--grad)}
.sh .hint{font-size:11.5px;color:var(--mut)}

/* ══════ slots ══════ */
.slots{display:grid;gap:15px;grid-template-columns:repeat(auto-fit,minmax(228px,1fr))}
.slot{position:relative;overflow:hidden;padding:24px 20px 20px;border-radius:20px;display:flex;flex-direction:column;
  background:linear-gradient(170deg,rgba(21,29,48,.95),rgba(8,12,21,.97));
  border:1px solid var(--line);transition:.22s cubic-bezier(.2,.9,.3,1)}
.slot::before{content:'';position:absolute;inset:0;opacity:0;transition:.22s;
  background:radial-gradient(ellipse 90% 60% at 50% -10%,rgba(0,240,168,.18),transparent 62%)}
.slot:hover{transform:translateY(-6px);border-color:rgba(0,240,168,.42);box-shadow:0 26px 54px rgba(0,0,0,.55),0 0 0 1px rgba(0,240,168,.18)}
.slot:hover::before{opacity:1}
.slot.hot{border-color:rgba(0,240,168,.55);box-shadow:0 0 0 1px rgba(0,240,168,.26),0 22px 50px rgba(0,240,168,.13)}
.slot.hot::after{content:'';position:absolute;top:0;left:20%;right:20%;height:2px;background:var(--grad);
  box-shadow:0 0 16px rgba(0,240,168,.8);border-radius:0 0 3px 3px}
.slot .tag{position:absolute;top:13px;right:13px;font-size:8.5px;font-weight:900;letter-spacing:1.1px;
  padding:4px 9px;border-radius:20px;background:rgba(0,240,168,.16);color:#9df7d3;border:1px solid rgba(0,240,168,.4)}
.slot .tag.p{background:rgba(160,108,255,.18);color:#cdb0ff;border-color:rgba(160,108,255,.42)}
.slot .hours{display:inline-flex;align-items:center;gap:6px;font-size:9.5px;font-weight:900;letter-spacing:1.2px;
  color:#ffd479;background:rgba(255,176,32,.12);border:1px solid rgba(255,176,32,.3);padding:4px 9px;border-radius:20px;margin-bottom:14px}
.slot .hours svg{width:11px;height:11px}
.slot .nm{font-size:10.5px;letter-spacing:2px;color:#8b98b1;font-weight:900;position:relative}
.slot .num{font-size:44px;font-weight:850;letter-spacing:-2.6px;line-height:1;margin:8px 0 0;position:relative;
  background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.slot .num span{font-size:12px;letter-spacing:.8px;font-weight:850;-webkit-text-fill-color:#78859f;color:#78859f}
.slot .price{font-size:24px;font-weight:850;margin-top:15px;letter-spacing:-.6px;position:relative;display:flex;align-items:baseline;gap:8px}
.slot .price s{font-size:13px;color:#4f5a70;font-weight:650}
.slot .save{font-size:9.5px;font-weight:900;color:#001b12;background:var(--gradg);padding:2px 7px;border-radius:6px;letter-spacing:.5px}
.slot ul{list-style:none;margin:15px 0 18px;display:flex;flex-direction:column;gap:8px;position:relative}
.slot li{display:flex;align-items:center;gap:8px;font-size:11.5px;color:#9aa7bd}
.slot li svg{width:13px;height:13px;color:var(--gr);flex:0 0 13px}
.slot .btn{margin-top:auto;position:relative}

/* steps */
.steps{display:grid;gap:13px;grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}
.step{position:relative;padding:20px 18px;border-radius:17px;background:rgba(255,255,255,.028);border:1px solid var(--line);overflow:hidden}
.step .n{width:29px;height:29px;border-radius:10px;background:rgba(0,240,168,.13);border:1px solid rgba(0,240,168,.42);
  color:var(--gr);display:grid;place-items:center;font-size:12.5px;font-weight:900;margin-bottom:12px}
.step b{display:block;font-size:13.5px;margin-bottom:6px;letter-spacing:-.1px}
.step p{font-size:11.5px;color:var(--mut);line-height:1.72}
.step .arc{position:absolute;right:-20px;bottom:-20px;width:70px;height:70px;border-radius:50%;
  border:1px solid rgba(0,240,168,.12)}

/* ══════ table ══════ */
.tw{overflow:auto;border-radius:17px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-size:9px;letter-spacing:1.5px;color:var(--mut);font-weight:900;padding:14px 15px;
  border-bottom:1px solid var(--line);background:rgba(255,255,255,.022);white-space:nowrap}
td{padding:14px 15px;border-bottom:1px solid rgba(122,142,180,.075);vertical-align:middle}
tr:last-child td{border-bottom:0}
tbody tr{transition:.14s}
tbody tr:hover td{background:rgba(255,255,255,.026)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;color:#c3cee3;letter-spacing:.3px}
.pcell{display:flex;align-items:center;gap:10px}
.pav{width:31px;height:31px;border-radius:9px;background:linear-gradient(135deg,#22304c,#141d2e);border:1px solid var(--line2);
  display:grid;place-items:center;font-size:11.5px;font-weight:850;color:#9df7d3;flex:0 0 31px;text-transform:uppercase}
.pnm{font-weight:800;font-size:12.5px;line-height:1.3}
.pid{font-size:10px;color:var(--mut2);font-family:ui-monospace,Menlo,monospace}
.pill{display:inline-flex;align-items:center;gap:5px;font-size:9px;font-weight:900;letter-spacing:.8px;
  padding:4px 9px;border-radius:20px;border:1px solid;white-space:nowrap}
.pill::before{content:'';width:5px;height:5px;border-radius:50%;background:currentColor}
.p-on{background:rgba(0,240,168,.1);border-color:rgba(0,240,168,.4);color:#8bf7d0}
.p-wait{background:rgba(255,176,32,.1);border-color:rgba(255,176,32,.4);color:#ffd479}
.p-off{background:rgba(122,142,180,.1);border-color:rgba(122,142,180,.3);color:#a2aec4}
.p-bad{background:rgba(255,77,109,.1);border-color:rgba(255,77,109,.4);color:#ff9aab}
.lvl{display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:23px;padding:0 8px;
  border-radius:7px;background:rgba(46,168,255,.13);border:1px solid rgba(46,168,255,.32);
  color:#8ecdff;font-size:11px;font-weight:900}
.expbar{width:70px;height:4px;border-radius:4px;background:rgba(255,255,255,.09);overflow:hidden;margin-top:5px}
.expbar i{display:block;height:100%;background:var(--grad);border-radius:4px}
.empty{padding:52px 20px;text-align:center;color:var(--mut);font-size:12.5px;line-height:1.9}
.empty svg{width:46px;height:46px;opacity:.28;margin-bottom:14px}
.empty b{display:block;color:#c5cfe1;font-size:13.5px;font-weight:800;margin-bottom:5px}
.skel{height:13px;border-radius:6px;background:linear-gradient(90deg,rgba(255,255,255,.05),rgba(255,255,255,.11),rgba(255,255,255,.05));
  background-size:200% 100%;animation:sk 1.3s infinite}
@keyframes sk{0%{background-position:200% 0}100%{background-position:-200% 0}}

/* ══════ feature cards (add id) ══════ */
.split{display:grid;gap:16px;grid-template-columns:1.4fr 1fr}
.side-card{padding:22px;display:flex;flex-direction:column}
.big-left{font-size:46px;font-weight:850;letter-spacing:-2px;line-height:1;
  background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.flist{display:flex;flex-direction:column;gap:10px;font-size:12px;color:#9aa7bd;margin-top:18px}
.flist div{display:flex;align-items:center;gap:9px}
.flist svg{width:14px;height:14px;color:var(--gr);flex:0 0 14px}

/* ══════ modal ══════ */
.ov{position:fixed;inset:0;background:rgba(2,4,8,.82);backdrop-filter:blur(9px);display:none;place-items:center;padding:18px;z-index:90}
.ov.open{display:grid}
.modal{width:100%;max-width:456px;border-radius:23px;padding:27px;position:relative;
  background:linear-gradient(172deg,#121a2c,#080d17);border:1px solid var(--line2);
  box-shadow:0 44px 100px rgba(0,0,0,.8),inset 0 1px 0 rgba(255,255,255,.05);
  animation:pop .26s cubic-bezier(.2,1.15,.4,1)}
.modal::before{content:'';position:absolute;top:0;left:22%;right:22%;height:2px;background:var(--grad);
  border-radius:0 0 4px 4px;box-shadow:0 0 16px rgba(0,240,168,.8)}
@keyframes pop{from{opacity:0;transform:scale(.94) translateY(12px)}to{opacity:1;transform:none}}
.modal .x{position:absolute;right:15px;top:15px;width:32px;height:32px;border-radius:10px;border:1px solid var(--line);
  background:rgba(255,255,255,.05);color:#a2aec4;cursor:pointer;display:grid;place-items:center;font-size:17px;line-height:1;transition:.15s}
.modal .x:hover{background:rgba(255,255,255,.11);color:#fff}
.modal h3{font-size:20px;font-weight:850;letter-spacing:-.3px;margin-bottom:6px}
.modal .m-sub{color:var(--mut);font-size:12.5px;line-height:1.65;margin-bottom:19px}
.sum{background:rgba(2,5,10,.6);border:1px solid var(--line);border-radius:15px;padding:16px;margin-bottom:16px}
.sum .r{display:flex;justify-content:space-between;align-items:center;font-size:12.5px;padding:6px 0;color:var(--mut)}
.sum .r b{color:#fff;font-size:13px;font-weight:800}
.sum .r.tot{border-top:1px dashed var(--line2);margin-top:8px;padding-top:13px;font-size:13px}
.sum .r.tot b{font-size:21px;color:var(--gr);font-weight:850;letter-spacing:-.5px}
.tgc{display:flex;align-items:center;gap:13px;padding:15px;border-radius:15px;margin-bottom:16px;
  background:linear-gradient(135deg,rgba(42,171,238,.15),rgba(0,240,168,.08));border:1px solid rgba(42,171,238,.32)}
.tgc .ava{width:43px;height:43px;border-radius:50%;background:linear-gradient(135deg,#2AABEE,#1487bd);
  display:grid;place-items:center;flex:0 0 43px;box-shadow:0 7px 20px rgba(42,171,238,.42)}
.tgc .ava svg{width:22px;height:22px;fill:#fff}
.tgc b{display:block;font-size:15px;letter-spacing:.1px}
.tgc small{color:var(--mut);font-size:11.5px}
.oidrow{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 14px;border-radius:12px;
  background:rgba(2,5,10,.7);border:1px dashed var(--line2);margin-bottom:16px}
.oidrow .l{font-size:9px;letter-spacing:1.4px;color:var(--mut2);font-weight:900}
.oidrow .v{font-family:ui-monospace,Menlo,monospace;font-size:14px;color:#fff;font-weight:700;letter-spacing:1px}
.note{margin-top:14px;font-size:11.5px;line-height:1.7;padding:12px 14px;border-radius:12px;
  background:rgba(255,176,32,.07);border:1px solid rgba(255,176,32,.22);color:#dcc79c}

/* ══════ toast ══════ */
.toast{position:fixed;bottom:26px;left:50%;transform:translateX(-50%) translateY(100px);
  padding:14px 20px;border-radius:13px;font-size:13px;font-weight:750;opacity:0;transition:.3s cubic-bezier(.2,.9,.3,1);
  z-index:100;max-width:92vw;background:#111a2b;border:1px solid var(--line2);
  box-shadow:0 26px 64px rgba(0,0,0,.75);backdrop-filter:blur(14px);display:flex;align-items:center;gap:9px}
.toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.ok{border-color:rgba(0,240,168,.5);color:#a8f7d8}
.toast.bad{border-color:rgba(255,77,109,.5);color:#ffa8b7}

/* ══════ admin ══════ */
.adm-tabs{display:flex;gap:7px;margin-bottom:16px}
.adm-tabs button{height:36px;padding:0 15px;border-radius:10px;background:rgba(255,255,255,.04);
  border:1px solid var(--line);color:#93a0b8;font:inherit;font-size:12.5px;font-weight:800;cursor:pointer;transition:.15s}
.adm-tabs button.on{background:rgba(0,240,168,.14);border-color:rgba(0,240,168,.4);color:#fff}
.slotctl{display:flex;gap:5px;align-items:center}
.slotctl .inp{height:32px;width:58px;padding:0 8px;font-size:12px;border-radius:8px;text-align:center}

/* ══════ responsive ══════ */
@media(max-width:860px){
  .split{grid-template-columns:1fr}
  .hero{padding:22px 18px}
  .hero h2{font-size:21px}
}
@media(max-width:640px){
  .wrap{padding:14px 13px 56px}
  .brand h1{font-size:14.5px}
  .brand small{font-size:8.5px;letter-spacing:1.8px}
  .mark{width:38px;height:38px;flex:0 0 38px;border-radius:12px}
  .mark svg{width:20px;height:20px}
  .chip{height:32px;padding:0 10px;font-size:11px}
  .avatar{width:32px;height:32px;flex:0 0 32px;font-size:12px}
  .auth{padding:24px 19px}
  .hero h2{font-size:19px}
  .stat .v{font-size:25px}
  .slot .num{font-size:38px}
  .modal{padding:22px 18px}
  th,td{padding:11px 11px}
  .hdr-r{gap:6px}
  .tabs button{padding:0 12px;font-size:12px}
  .tabs button span{display:none}
}
@media(max-width:400px){
  .chip.usr{display:none}
}

/* ════════ redeem ════════ */
.rd-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:18px;align-items:start}
.rd-card{padding:28px}
.rd-card h3{font-size:19px;font-weight:850;letter-spacing:-.3px;margin:14px 0 0}
.rd-sub{font-size:12.5px;color:var(--mut);margin-top:6px;line-height:1.6}
.rd-ic{width:52px;height:52px;border-radius:16px;display:grid;place-items:center;
  background:linear-gradient(135deg,rgba(0,240,168,.2),rgba(0,240,168,.05));border:1px solid rgba(0,240,168,.35);color:#00f0a8}
.rd-ic svg{width:26px;height:26px}
.rd-inp{font-family:ui-monospace,monospace;letter-spacing:2.5px;font-weight:850;font-size:16px;text-transform:uppercase;text-align:center;height:56px!important}
.rd-side{padding:26px;display:flex;flex-direction:column;position:relative;overflow:hidden}
.rd-big{font-size:60px;font-weight:900;letter-spacing:-2.5px;line-height:1;
  background:linear-gradient(135deg,#00f0a8,#5edcff);-webkit-background-clip:text;background-clip:text;color:transparent}
.rd-lbl{font-size:11px;letter-spacing:1.4px;color:var(--mut);font-weight:850;margin-top:4px;text-transform:uppercase}
.rd-timer{margin-top:16px;display:inline-flex;align-items:center;gap:8px;font-size:12px;color:#cfe0f5;
  background:rgba(255,176,32,.1);border:1px solid rgba(255,176,32,.32);border-radius:11px;padding:10px 14px;font-weight:650}
.rd-timer b{color:#ffd479;font-variant-numeric:tabular-nums;font-weight:850}
.cgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}
.cgrid .inp{font-size:12.5px}
select.inp{appearance:none;background-image:linear-gradient(45deg,transparent 50%,#7d8aa3 50%),linear-gradient(135deg,#7d8aa3 50%,transparent 50%);
  background-position:calc(100% - 18px) 21px,calc(100% - 13px) 21px;background-size:5px 5px,5px 5px;background-repeat:no-repeat;cursor:pointer}
select.inp option{background:#0e1520;color:#e6eefc}
.btn.dan{background:rgba(255,70,90,.14);border:1px solid rgba(255,70,90,.4);color:#ff8f9d}
.btn.dan:hover{background:rgba(255,70,90,.24)}
.msg.ok{color:#00f0a8}
@media(max-width:900px){.rd-grid{grid-template-columns:1fr}}
@media(max-width:760px){.cgrid{grid-template-columns:1fr 1fr}}
@media(max-width:460px){.cgrid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="amb"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div><div class="grid-ov"></div></div>
<div class="vig"></div>

<!-- ═══════════════ AUTH ═══════════════ -->
<div class="wrap" id="authView">
  <div class="top">
    <div class="brand">
      <div class="mark"><svg viewBox="0 0 24 24" fill="none" stroke="#001b12" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.6s4.9 4.4 4.9 8.6a4.9 4.9 0 0 1-9.8 0c0-1.6.8-3.1 1.6-4.1.3 1.3 1.1 2 1.8 2.3.6-2.4 1.5-4.6 1.5-6.8z"/></svg></div>
      <div><h1>CHINNU <b>LEVEL PRO</b></h1><small>FREE FIRE LEVEL UP</small></div>
    </div>
    <div class="hdr-r"><div class="chip"><span class="dot-live"></span> All systems live</div></div>
  </div>

  <div class="auth-wrap">
    <div class="glass auth">
      <div class="kicker">FREE FIRE LEVEL UP PANEL</div>
      <h2 id="authTitle">Welcome back</h2>
      <div class="sub" id="authSub">Sign in to manage your slots, IDs and EXP — all in one place</div>
      <div class="seg">
        <button id="tabLogin" class="on" onclick="setAuth('login')">Login</button>
        <button id="tabReg" onclick="setAuth('reg')">Create Account</button>
      </div>
      <form id="authForm" onsubmit="return false">
        <div class="fld"><label>USERNAME</label><input class="inp" id="au" placeholder="your username" autocomplete="username" spellcheck="false"></div>
        <div class="fld"><label>PASSWORD</label><input class="inp" id="ap" type="password" placeholder="••••••••" autocomplete="current-password"></div>
        <button class="btn pri blk" id="authGo" style="margin-top:8px">Login</button>
      </form>
      <div class="msg" id="authMsg"></div>
      <div class="foot">
        Slots kinte <a href="https://t.me/sbg_mod" target="_blank" rel="noopener">Telegram @sbg_mod</a>
        <div style="opacity:.6;margin-top:5px;font-size:11px">Secure login · instant slots · 24/7 bot</div>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════ APP ═══════════════ -->
<div class="wrap" id="appView" style="display:none">
  <div class="top">
    <div class="brand">
      <div class="mark"><svg viewBox="0 0 24 24" fill="none" stroke="#001b12" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.6s4.9 4.4 4.9 8.6a4.9 4.9 0 0 1-9.8 0c0-1.6.8-3.1 1.6-4.1.3 1.3 1.1 2 1.8 2.3.6-2.4 1.5-4.6 1.5-6.8z"/></svg></div>
      <div><h1>CHINNU <b>LEVEL PRO</b></h1><small>FREE FIRE LEVEL UP</small></div>
    </div>
    <div class="hdr-r">
      <div class="chip slot">SLOTS <b id="chipSlots">–</b></div>
      <div class="chip usr"><div class="avatar" id="hdrAv">U</div><b id="chipUser">user</b></div>
      <button class="btn sm" onclick="logout()">Logout</button>
    </div>
  </div>

  <div class="tabs" id="tabs">
    <button data-v="dash" class="on"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="2"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2"/></svg><span>Dashboard</span></button>
    <button data-v="buy"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.8l2.9 5.9 6.5.95-4.7 4.6 1.1 6.5L12 17.6l-5.8 3.15 1.1-6.5-4.7-4.6 6.5-.95z"/></svg><span>Buy Slots</span></button>
    <button data-v="redeem"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8V6.5A1.5 1.5 0 0 1 5.5 5h13A1.5 1.5 0 0 1 20 6.5V8"/><path d="M9.5 19h5"/><path d="M12 5v14"/><path d="M4 8h16"/><path d="M7 12h2M15 12h2M7 15.5h2M15 15.5h2"/></svg><span>Redeem</span></button>
    <button data-v="ids"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="8" r="3.6"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/></svg><span>My IDs</span> <span class="cnt" id="idsTabCnt">0</span></button>
    <button data-v="add"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg><span>Add ID</span></button>
    <button data-v="how"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.4a2.6 2.6 0 0 1 5 .9c0 1.9-2.5 2.1-2.5 3.9"/><circle cx="12" cy="17.3" r=".9" fill="currentColor" stroke="none"/></svg><span>Guide</span></button>
    <button data-v="admin" id="tabAdmin" style="display:none"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3l7.5 3.2v5.4c0 4.6-3.1 8.3-7.5 9.4-4.4-1.1-7.5-4.8-7.5-9.4V6.2z"/></svg><span>Admin</span></button>
  </div>

  <!-- DASHBOARD -->
  <section class="view on" id="v-dash">
    <div class="glass hero">
      <div class="badge24">LIVE DASHBOARD</div>
      <h2>Welcome back, <em id="heroName">Chinnu</em></h2>
      <p>Your Free Fire accounts, slots and EXP — all in one place. Bot runs 24/7.</p>
      <div class="row">
        <button class="btn pri" onclick="go('buy')"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" style="margin-right:-2px"><path d="M12 2.8l2.9 5.9 6.5.95-4.7 4.6 1.1 6.5L12 17.6l-5.8 3.15 1.1-6.5-4.7-4.6 6.5-.95z"/></svg> Buy Slots</button>
        <button class="btn" onclick="go('redeem')">Redeem Code</button>
        <button class="btn" onclick="go('add')">Add ID</button>
      </div>
      <div class="timer" id="hdrTimer" style="display:none">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 1.8"/></svg>
        Slot expiry — <b id="timerVal">--:--:--</b> baki (ei somoy por slot auto off)
      </div>
    </div>
    <div class="stats">
      <div class="stat g"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="#00f0a8" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="8" r="3.6"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/></svg>
        <div class="k">MY IDS</div><div class="v" id="stIds">0</div><div class="b"><i id="barIds" style="width:0%"></i></div></div>
      <div class="stat b"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="#2ea8ff" stroke-width="2" stroke-linecap="round"><path d="M13 2.5L4.5 13.5H11l-1 8 8.5-11H12z"/></svg>
        <div class="k">ONLINE NOW</div><div class="v" id="stOnline">0</div><div class="b"><i id="barOn" style="width:0%;background:linear-gradient(135deg,#2ea8ff,#1e7fd4)"></i></div></div>
      <div class="stat v"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="#a06cff" stroke-width="2" stroke-linecap="round"><path d="M3 17l5-6 4 3 5-8 4 5"/></svg>
        <div class="k">EXP GAINED</div><div class="v" id="stExp">0</div></div>
      <div class="stat a"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="#ffb020" stroke-width="2" stroke-linecap="round"><rect x="3" y="6" width="18" height="13" rx="3"/><path d="M3 10h18M7 15h4"/></svg>
        <div class="k">SLOTS LEFT</div><div class="v" id="stSlots">–</div><div class="b"><i id="barSlots" style="width:0%;background:linear-gradient(135deg,#ffb020,#ff8a00)"></i></div></div>
    </div>
    <div class="sh"><h3>MY ACCOUNTS</h3><span class="hint" id="accHint"></span></div>
    <div class="glass tw">
      <table><thead><tr><th>PLAYER</th><th>UID</th><th>LEVEL</th><th>EXP</th><th>STATUS</th><th></th></tr></thead>
      <tbody id="accBody"><tr><td colspan="6" style="padding:26px"><div class="skel" style="width:60%"></div></td></tr></tbody></table>
    </div>
  </section>

  <!-- BUY SLOTS -->
  <section class="view" id="v-buy">
    <div class="glass hero" style="margin-bottom:20px">
      <div class="badge24">SLOTS STORE</div>
      <h2>Buy <em>Slots</em> — 1 slot = 1 ID</h2>
      <p>Hit Buy → <b>your Telegram chat opens directly</b> with the order details. Once payment is done, admin activates your slots.</p>
    </div>
    <div class="slots" id="slotGrid"></div>
    <div class="sh"><h3>HOW PAYMENT WORKS</h3><span class="hint">Telegram only · instant activate</span></div>
    <div class="steps">
      <div class="step"><div class="arc"></div><div class="n">1</div><b>Pick a plan</b><p>Compare slots and price, then hit Buy.</p></div>
      <div class="step"><div class="arc"></div><div class="n">2</div><b>Hit Buy</b><p>The moment you press Buy, Telegram <b>@sbg_mod</b> opens with your order ID pre-filled.</p></div>
      <div class="step"><div class="arc"></div><div class="n">3</div><b>Make payment</b><p>Pay via UPI/bank and send the screenshot on Telegram.</p></div>
      <div class="step"><div class="arc"></div><div class="n">4</div><b>Slots activated</b><p>As soon as admin approves, slots are credited and the dashboard timer starts.</p></div>
    </div>
  </section>

  <!-- REDEEM CODE -->
  <section class="view" id="v-redeem">
    <div class="glass hero" style="margin-bottom:20px">
      <div class="badge24">REDEEM CODE</div>
      <h2>Enter a code, <em>get slots</em></h2>
      <p>Enter your redeem code — <b>slots and validity are added instantly</b>. No payment needed.</p>
    </div>
    <div class="rd-grid">
      <div class="glass rd-card">
        <div class="rd-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8V6.5A1.5 1.5 0 0 1 5.5 5h13A1.5 1.5 0 0 1 20 6.5V8"/><path d="M9.5 19h5"/><path d="M12 5v14"/><path d="M4 8h16"/></svg></div>
        <h3>Enter Redeem Code</h3>
        <p class="rd-sub">Type the code carefully — it is not case sensitive</p>
        <div class="fld" style="margin-top:18px"><label>REDEEM CODE</label>
          <input class="inp rd-inp" id="rdIn" placeholder="CHINNU-XXXXXX" autocomplete="off" spellcheck="false"></div>
        <button class="btn pri blk" id="rdGo" style="margin-top:8px">Redeem Now</button>
        <div class="msg" id="rdMsg"></div>
      </div>
      <div class="glass rd-side">
        <div class="sh" style="margin:0 0 14px"><h3>MY SLOTS</h3></div>
        <div class="rd-big" id="rdSlots">0</div>
        <div class="rd-lbl">slots active</div>
        <div class="rd-timer" id="rdTimer" style="display:none">Expires in <b id="rdTv">--:--:--</b></div>
        <div class="flist" style="margin-top:20px">
          <div><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6.5L9.5 17 4 11.5"/></svg> One code = one use</div>
          <div><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6.5L9.5 17 4 11.5"/></svg> Instant credit, zero waiting</div>
          <div><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6.5L9.5 17 4 11.5"/></svg> Validity starts automatically</div>
        </div>
        <button class="btn blk" style="margin-top:auto" onclick="go('buy')">Don't have a code? Buy Slots</button>
      </div>
    </div>
  </section>

  <!-- MY IDS -->
  <section class="view" id="v-ids">
    <div class="sh" style="margin-top:0"><h3>MY IDS</h3><span class="hint"><span id="idsCount">0</span> ID · <span id="idsSlots">0</span> slot used</span></div>
    <div class="glass tw">
      <table><thead><tr><th>PLAYER</th><th>UID</th><th>LEVEL</th><th>EXP GAINED</th><th>MATCHES</th><th>STATUS</th><th></th></tr></thead>
      <tbody id="idsBody"><tr><td colspan="7" style="padding:26px"><div class="skel" style="width:55%"></div></td></tr></tbody></table>
    </div>
  </section>

  <!-- ADD ID -->
  <section class="view" id="v-add">
    <div class="split">
      <div class="glass" style="padding:24px">
        <h3 style="font-size:17px;font-weight:850;letter-spacing:-.2px">Add Free Fire ID</h3>
        <div style="font-size:12px;color:var(--mut);margin:6px 0 20px;line-height:1.65">Add an account — the bot runs 24/7 and collects EXP automatically.</div>
        <div class="fld"><label>PLAYER UID</label><input class="inp" id="aUid" placeholder="e.g. 8496814458" inputmode="numeric"></div>
        <div class="fld"><label>PASSWORD</label><input class="inp" id="aPwd" type="password" placeholder="account password"></div>
        <div class="fld"><label>NAME <i>(optional)</i></label><input class="inp" id="aName" placeholder="nickname"></div>
        <button class="btn pri blk" id="aGo" style="margin-top:6px">Add ID &amp; Start Bot</button>
        <div class="msg" id="aMsg"></div>
      </div>
      <div class="glass side-card">
        <div style="font-size:9.5px;letter-spacing:1.5px;color:var(--mut);font-weight:900">SLOTS BAKI</div>
        <div class="big-left" id="addSlotsLeft" style="margin-top:10px">–</div>
        <div style="font-size:11.5px;color:var(--mut);margin-top:8px">1 ID = 1 slot · slot active 24h</div>
        <div class="flist">
          <div><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6.5L9.5 17 4 11.5"/></svg> Bot 24/7 auto run</div>
          <div><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6.5L9.5 17 4 11.5"/></svg> EXP auto collect</div>
          <div><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6.5L9.5 17 4 11.5"/></svg> Delete → slot free</div>
          <div><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6.5L9.5 17 4 11.5"/></svg> Password encrypted</div>
        </div>
        <button class="btn blk" style="margin-top:auto" onclick="go('buy')">Buy more slots</button>
      </div>
    </div>
  </section>

  <!-- GUIDE -->
  <section class="view" id="v-how">
    <div class="glass hero" style="margin-bottom:20px">
      <div class="badge24">GUIDE</div>
      <h2>How it <em>works</em></h2>
      <p>Get your Free Fire account levelling up in 3 simple steps.</p>
    </div>
    <div class="steps">
      <div class="step"><div class="n">1</div><b>Buy slots</b><p>Buy Slots → pick a plan → hit Buy → Telegram chat opens → pay → admin approves = slots active.</p></div>
      <div class="step"><div class="n">2</div><b>Add your ID</b><p>Add ID → enter UID + password → the bot starts and you can watch the live status on your dashboard.</p></div>
      <div class="step"><div class="n">3</div><b>Collect EXP</b><p>The bot plays BR Evo matches and collects EXP — levelling up is automatic.</p></div>
    </div>
    <div class="glass" style="padding:24px;margin-top:16px">
      <div class="sh" style="margin:0 0 14px"><h3>IMPORTANT</h3></div>
      <div style="font-size:12.5px;color:#9aa7bd;line-height:2.1">
        · 1 slot = 1 ID · deleting an ID frees the slot<br>
        · Slots stay active for 24 hours — then they expire automatically and you need to buy again (your account/password keeps working)<br>
        · Never share your password · panel is secure (PBKDF2 hash)<br>
        · Any problem? Reach us on Telegram <a href="https://t.me/sbg_mod" target="_blank" rel="noopener" style="color:#5edcff;font-weight:750">@sbg_mod</a>
      </div>
    </div>
  </section>

  <!-- ADMIN -->
  <section class="view" id="v-admin">
    <div class="adm-tabs">
      <button id="atU" class="on" onclick="admTab('u')">Users</button>
      <button id="atO" onclick="admTab('o')">Orders</button>
      <button id="atC" onclick="admTab('c')">Redeem Codes</button>
    </div>
    <div id="admU">
      <div class="sh" style="margin-top:0"><h3>USERS</h3><span class="hint">Add, set or delete slots</span></div>
      <div class="glass tw"><table><thead><tr><th>USER</th><th>SLOTS</th><th>USED</th><th>EXPIRES IN</th><th>SLOT CONTROL</th><th></th></tr></thead>
      <tbody id="admUsers"><tr><td colspan="6" style="padding:26px"><div class="skel" style="width:50%"></div></td></tr></tbody></table></div>
    </div>
    <div id="admO" style="display:none">
      <div class="sh" style="margin-top:0"><h3>ORDERS</h3><span class="hint">Verify payment and approve</span></div>
      <div class="glass tw"><table><thead><tr><th>ORDER</th><th>USER</th><th>PLAN</th><th>AMOUNT</th><th>STATUS</th><th>ACTION</th></tr></thead>
      <tbody id="admOrders"><tr><td colspan="6" style="padding:26px"><div class="skel" style="width:50%"></div></td></tr></tbody></table></div>
    </div>
    <div id="admC" style="display:none">
      <div class="glass" style="padding:20px;margin-bottom:18px">
        <div class="sh" style="margin:0 0 14px"><h3>NEW REDEEM CODE</h3><span class="hint">create a code → user redeems it</span></div>
        <div class="cgrid">
          <div class="fld" style="margin:0"><label>CODE (blank = auto)</label><input class="inp" id="cCode" placeholder="CHINNU-ABC123" style="text-transform:uppercase"></div>
          <div class="fld" style="margin:0"><label>SLOTS</label><input class="inp" id="cSlots" type="number" min="1" placeholder="10"></div>
          <div class="fld" style="margin:0"><label>VALIDITY (hours)</label><input class="inp" id="cHours" type="number" min="1" placeholder="24"></div>
          <div class="fld" style="margin:0"><label>USES (0 = ∞)</label><input class="inp" id="cLimit" type="number" min="0" placeholder="1"></div>
          <div class="fld" style="margin:0"><label>LABEL</label><input class="inp" id="cLabel" placeholder="Eid gift"></div>
          <div class="fld" style="margin:0"><label>PREFIX (auto)</label><input class="inp" id="cPrefix" placeholder="CHINNU"></div>
        </div>
        <button class="btn pri blk" id="cGo" style="margin-top:4px">Generate Redeem Code</button>
        <div class="msg" id="cMsg"></div>
      </div>
      <div class="sh" style="margin-top:0"><h3>ALL REDEEM CODES</h3><span class="hint" id="cCount">0 codes</span></div>
      <div class="glass tw"><table><thead><tr><th>CODE</th><th>GIVES</th><th>USED</th><th>VALIDITY</th><th>STATUS</th><th></th></tr></thead>
      <tbody id="admCodes"><tr><td colspan="6" style="padding:26px"><div class="skel" style="width:50%"></div></td></tr></tbody></table></div>
    </div>
  </section>
</div>

<!-- BUY MODAL -->
<div class="ov" id="ov">
  <div class="modal">
    <button class="x" onclick="closeOv()">×</button>
    <h3>Confirm Order</h3>
    <div class="m-sub">Order details go straight to Telegram — complete payment and admin will verify.</div>
    <div class="sum">
      <div class="r"><span>Plan</span><b id="moPlan">—</b></div>
      <div class="r"><span>Slots</span><b id="moSlots">—</b></div>
      <div class="r"><span>Validity</span><b id="moVal" style="color:#ffd479">24 hours</b></div>
      <div class="r tot"><span>Total payable</span><b id="moPrice">—</b></div>
    </div>
    <div class="tgc">
      <div class="ava"><svg viewBox="0 0 24 24"><path d="M21.9 4.3l-3.1 14.6c-.2 1-.9 1.3-1.8.8l-4.9-3.6-2.4 2.3c-.3.3-.5.5-1 .5l.3-4.9 8.9-8c.4-.3-.1-.5-.6-.2L6.5 12.4 1.7 10.9c-1-.3-1-1 .2-1.5l18.6-7.2c.9-.3 1.6.2 1.4 2.1z"/></svg></div>
      <div><b>@sbg_mod</b><small>Telegram — payment &amp; activation</small></div>
    </div>
    <div class="oidrow"><div><div class="l">ORDER ID</div><div class="v" id="moId">…</div></div>
      <button class="btn xs" onclick="copyOid()">Copy</button></div>
    <button class="btn tg blk" id="moGo">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="#fff"><path d="M21.9 4.3l-3.1 14.6c-.2 1-.9 1.3-1.8.8l-4.9-3.6-2.4 2.3c-.3.3-.5.5-1 .5l.3-4.9 8.9-8c.4-.3-.1-.5-.6-.2L6.5 12.4 1.7 10.9c-1-.3-1-1 .2-1.5l18.6-7.2c.9-.3 1.6.2 1.4 2.1z"/></svg>
      Send on Telegram / Pay
    </button>
    <div class="note">Pressing Buy opens the <b>@sbg_mod chat directly</b> — order ID, slots and amount are already written. Send the payment screenshot and admin will approve.</div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
/* ════════ helpers ════════ */
const $ = id => document.getElementById(id);
const nf = n => Number(n||0).toLocaleString('en-IN');
const esc = s => String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ini = s => (String(s||'?').trim()[0]||'?').toUpperCase();
function toast(t, bad){ const e=$('toast'); e.textContent=t; e.className='toast on'+(bad?' bad':' ok');
  clearTimeout(e._t); e._t=setTimeout(()=>e.className='toast',3400); }
async function api(url, body){
  const o = body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {};
  const r = await fetch(url, o);
  const d = await r.json().catch(()=>({}));
  if(r.status===401) throw new Error('login');
  if(!r.ok || d.status==='error') throw new Error(d.error || ('HTTP '+r.status));
  return d;
}

/* ════════ plans — all 24h ════════ */
const PLANS = [
  {id:'p3',  slots:3,  price:20,  hours:24, name:'TRIAL',    tag:'',           hot:false, mrp:30},
  {id:'p5',  slots:5,  price:30,  hours:24, name:'STARTER',  tag:'',           hot:false, mrp:45},
  {id:'p10', slots:10, price:50,  hours:24, name:'POPULAR',  tag:'BEST VALUE', hot:true,  mrp:80},
  {id:'p25', slots:25, price:100, hours:24, name:'PRO',      tag:'SAVE 20%',   hot:false, mrp:150},
  {id:'p50', slots:50, price:180, hours:24, name:'BUSINESS', tag:'SAVE 28%',   hot:false, mrp:280},
];
const TG = 'sbg_mod';
let ME=null, CUR=null, TICK=null;

/* ════════ auth ════════ */
let AMODE='login';
function setAuth(m){
  AMODE=m;
  $('tabLogin').classList.toggle('on', m==='login');
  $('tabReg').classList.toggle('on', m==='reg');
  $('authGo').textContent = m==='reg' ? 'Create Account' : 'Login';
  $('authTitle').textContent = m==='reg' ? 'Create account' : 'Welcome back';
  $('authSub').textContent = m==='reg' ? 'Create a new account — buy slots and add your IDs' : 'Sign in to manage your slots, IDs and EXP — all in one place';
  $('authMsg').className='msg';
}
async function authGo(){
  const u=$('au').value.trim(), p=$('ap').value, m=$('authMsg');
  if(!u||!p){ m.className='msg err'; m.textContent='Please enter username and password'; return; }
  const b=$('authGo'), old=b.textContent; b.disabled=true; b.textContent='Please wait…';
  try{
    const ep = AMODE==='reg' ? '/api/panel/register' : '/api/panel/login';
    const d = await api(ep, {username:u, password:p});
    m.className='msg ok'; m.textContent='Welcome '+d.username+' — loading…';
    setTimeout(boot, 420);
  }catch(e){ m.className='msg err'; m.textContent=e.message; }
  finally{ b.disabled=false; b.textContent=old; }
}
$('authGo').addEventListener('click', authGo);
$('ap').addEventListener('keydown', e=>{ if(e.key==='Enter') authGo(); });
$('au').addEventListener('keydown', e=>{ if(e.key==='Enter') $('ap').focus(); });
function logout(){ fetch('/api/panel/logout',{method:'POST'}).finally(()=>location.reload()); }

/* ════════ nav ════════ */
function go(v){
  if(v==='admin' && !(ME && ME.admin)) return;   /* user ke liye admin view block */
  document.querySelectorAll('.view').forEach(s=>s.classList.toggle('on', s.id==='v-'+v));
  document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on', b.dataset.v===v));
  window.scrollTo({top:0,behavior:'smooth'});
  if(v==='dash'||v==='ids') loadStats();
  if(v==='admin'){ loadAdmUsers(); loadAdmOrders(); loadAdmCodes(); }
  if(v==='redeem'){ $('rdSlots').textContent = (ME&&ME.slots)||0; }
}
document.querySelectorAll('#tabs button').forEach(b=>b.addEventListener('click',()=>go(b.dataset.v)));

/* ════════ boot ════════ */
async function boot(){
  let me;
  try{ me = await api('/api/panel/me'); }catch(e){ return showAuth(); }
  ME = me;
  $('authView').style.display='none';
  $('appView').style.display='block';
  $('chipUser').textContent = me.username;
  $('hdrAv').textContent = ini(me.username);
  $('heroName').textContent = me.username;
  $('tabAdmin').style.display = me.admin ? 'flex' : 'none';
  updSlots(); renderPlans(); startTimer(); loadStats();
}
async function refresh(){
  try{ ME = await api('/api/panel/me'); }catch(e){ return; }
  $('heroName').textContent = ME.username;
  updSlots(); startTimer(); loadStats();
}
function showAuth(){ $('authView').style.display='block'; $('appView').style.display='none'; var t=$('tabAdmin'); if(t) t.style.display='none'; ME=null; try{ if(typeof AMODE!=='undefined' && AMODE!=='login') setAuth('login'); }catch(e){} var _ap=$('ap'); if(_ap) _ap.value=''; }

function updSlots(){
  const left = (ME && ME.left!=null) ? ME.left : '∞';
  $('chipSlots').textContent = left;
  $('stSlots').textContent = left;
  $('addSlotsLeft').textContent = left;
  const rd = $('rdSlots'); if(rd) rd.textContent = (ME && ME.slots) || 0;
  const total = (ME && ME.slots) || 1;
  $('barSlots').style.width = Math.min(100, Math.round(((ME&&ME.left)||0)/Math.max(1,total)*100))+'%';
}
/* ════════ 24h countdown ════════ */
function startTimer(){
  clearInterval(TICK);
  const el = $('hdrTimer');
  const tick = ()=>{
    const rEl = $('rdTimer');
    if(!ME || !ME.expires_at){ el.style.display='none'; if(rEl) rEl.style.display='none'; return; }
    const left = Number(ME.expires_at)*1000 - Date.now();
    if(left <= 0){ el.style.display='none'; if(rEl) rEl.style.display='none'; if(ME.left!==0){ ME.left=0; updSlots(); } return; }
    const h = Math.floor(left/3600000), m = Math.floor(left%3600000/60000), s = Math.floor(left%60000/1000);
    el.style.display='inline-flex';
    const t = String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
    $('timerVal').textContent = t;
    if(rEl){ rEl.style.display='inline-flex'; $('rdTv').textContent = t; }
  };
  tick(); TICK = setInterval(tick, 1000);
}
function expText(ts){
  if(!ts) return '<span style="color:#5b6780">—</span>';
  const left = Number(ts)*1000 - Date.now();
  if(left <= 0) return '<span class="pill p-bad">EXPIRED</span>';
  const h = Math.floor(left/3600000), m = Math.floor(left%3600000/60000);
  return '<span style="color:#9df7d3;font-weight:750">'+h+'h '+m+'m</span>';
}

/* ════════ slots render ════════ */
function renderPlans(){
  $('slotGrid').innerHTML = PLANS.map(p=>{
    const per = (p.price/p.slots).toFixed(1);
    const save = Math.round((1 - p.price/p.mrp)*100);
    return `<div class="slot ${p.hot?'hot':''}">
      ${p.tag?`<div class="tag ${p.hot?'':'p'}">${p.tag}</div>`:''}
      <div class="hours"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 1.8"/></svg> 24 HOURS</div>
      <div class="nm">${p.name}</div>
      <div class="num">${p.slots}<span> SLOTS</span></div>
      <div class="price">₹${p.price}<s>₹${p.mrp}</s>${save>0?`<span class="save">${save}% OFF</span>`:''}</div>
      <ul>
        <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6.5L9.5 17 4 11.5"/></svg> ₹${per} per slot</li>
        <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6.5L9.5 17 4 11.5"/></svg> Instant activate</li>
        <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6.5L9.5 17 4 11.5"/></svg> 24/7 bot support</li>
      </ul>
      <button class="btn ${p.hot?'pri':''}" onclick="buy('${p.id}')">Buy now</button>
    </div>`;
  }).join('');
}

/* ════════ buy → modal → telegram ════════ */
async function buy(planId){
  const p = PLANS.find(x=>x.id===planId); if(!p) return;
  $('moPlan').textContent = p.name+' plan';
  $('moSlots').textContent = p.slots+' slots';
  $('moVal').textContent = '24 hours';
  $('moPrice').textContent = '₹'+p.price;
  $('moId').textContent = '…';
  CUR = {id:'…', plan:p.id, slots:p.slots, amount:p.price};
  $('ov').classList.add('open');
  try{
    const d = await api('/api/panel/order/create', {plan:planId});
    CUR = d.order;
    $('moId').textContent = CUR.id;
  }catch(e){
    CUR.id = 'ORD'+Math.floor(1000+Math.random()*9000);
    $('moId').textContent = CUR.id;
  }
}
/* ════════ redeem code ════════ */
async function redeemNow(){
  const m = $('rdMsg'); const inp = $('rdIn');
  const code = (inp.value||'').trim().toUpperCase();
  if(!code){ m.className='msg err'; m.textContent='Please enter a code'; return; }
  const btn = $('rdGo'); btn.disabled = true; btn.textContent = 'Redeeming…';
  try{
    const d = await api('/api/panel/redeem', {code});
    m.className='msg ok';
    m.textContent = '✅ +'+d.slots_added+' slots added'+(d.label?' — '+d.label:'')+' · validity '+d.hours+'h';
    inp.value = '';
    toast('+'+d.slots_added+' slots redeemed!');
    await refresh();
  }catch(e){
    m.className='msg err'; m.textContent = e.message;
  }finally{
    btn.disabled = false; btn.textContent = 'Redeem Now';
  }
}
$('rdGo').addEventListener('click', redeemNow);
$('rdIn').addEventListener('keydown', e=>{ if(e.key==='Enter'){ e.preventDefault(); redeemNow(); } });
function closeOv(){ $('ov').classList.remove('open'); }
$('ov').addEventListener('click', e=>{ if(e.target===$('ov')) closeOv(); });
function copyOid(){ if(!CUR) return; navigator.clipboard?.writeText(CUR.id).then(()=>toast('Order ID copied')).catch(()=>{}); }
$('moGo').addEventListener('click', async ()=>{
  if(!CUR) return;
  const p = PLANS.find(x=>x.id===CUR.plan) || {name:'Plan'};
  let order = CUR;
  try{
    const d = await api('/api/panel/order/create', {plan:CUR.plan});
    order = d.order;
    $('moId').textContent = order.id;
  }catch(e){ toast(e.message,1); return; }
  const lines = ['Hello! I would like to place an order 👇','',
    '🆔 Order ID: '+order.id,
    '📦 Plan: '+p.name,
    '🎟 Slots: '+order.slots,
    '💰 Amount: Rs '+order.amount,
    '⏱ Validity: 24 hours'];
  lines.push('', 'Please share the payment details.');
  const url = `https://t.me/${TG}?text=${encodeURIComponent(lines.join('\n'))}`;
  const w = window.open(url, '_blank');
  if(!w){ location.href = url; }
  closeOv();
  toast('Telegram khulche — order '+order.id+' ready');
});

/* ════════ stats ════════ */
function statusPill(s){
  s = String(s||'').toUpperCase();
  if(s.includes('MATCH')||s==='ONLINE'||s==='PLAYING') return '<span class="pill p-on">'+s+'</span>';
  if(s.includes('CONNECT')||s.includes('LOGIN')||s.includes('WAIT')||s.includes('START')) return '<span class="pill p-wait">'+s+'</span>';
  if(s.includes('ERROR')||s.includes('FAIL')||s.includes('BAN')) return '<span class="pill p-bad">'+s+'</span>';
  return '<span class="pill p-off">'+(s||'OFFLINE')+'</span>';
}
function playerCell(a){
  const nm = a.nickname || ('Player_'+(a.uid||'').slice(0,6));
  return `<div class="pcell"><div class="pav">${esc(ini(nm))}</div>
    <div><div class="pnm">${esc(nm)}</div><div class="pid">${esc(a.uid||'-')}</div></div></div>`;
}
async function loadStats(){
  let d;
  try{ d = await api('/api/stats'); }catch(e){ if(e.message==='login') showAuth(); return; }
  const accs = d.accounts || [];
  const on = accs.filter(a=>{const s=String(a.status||'').toUpperCase();return s==='ONLINE'||s.includes('MATCH')||s==='PLAYING'}).length;
  $('stIds').textContent = nf(accs.length);
  $('stOnline').textContent = nf(on);
  $('stExp').textContent = nf(d.total_gained_exp);
  $('idsTabCnt').textContent = accs.length;
  $('idsCount').textContent = accs.length;
  $('idsSlots').textContent = accs.length;
  $('accHint').textContent = accs.length ? (on+' online · '+accs.length+' total') : '';
  const maxSlots = (ME && ME.slots) || Math.max(accs.length,1);
  $('barIds').style.width = Math.min(100, Math.round(accs.length/Math.max(1,maxSlots)*100))+'%';
  $('barOn').style.width = accs.length ? Math.round(on/accs.length*100)+'%' : '0%';

  $('accBody').innerHTML = accs.length ? accs.map(a=>`<tr>
      <td>${playerCell(a)}</td>
      <td class="mono">${esc(a.uid||'-')}</td>
      <td><span class="lvl">${a.level||1}</span></td>
      <td style="color:#00f0a8;font-weight:800">+${nf(a.gained_exp)}</td>
      <td>${statusPill(a.status)}</td>
      <td><button class="btn dan xs" onclick="delId('${esc(a.uid)}')">Delete</button></td></tr>`).join('')
    : emptyRow(6,'No IDs yet','Add your Free Fire account from the Add ID tab');

  $('idsBody').innerHTML = accs.length ? accs.map(a=>`<tr>
      <td>${playerCell(a)}</td>
      <td class="mono">${esc(a.uid||'-')}</td>
      <td><span class="lvl">${a.level||1}</span></td>
      <td><div style="color:#00f0a8;font-weight:800">+${nf(a.gained_exp)}</div>
        <div class="expbar"><i style="width:${Math.min(100,(a.gained_exp%5000)/50)}%"></i></div></td>
      <td>${nf(a.matches_played)}</td>
      <td>${statusPill(a.status)}</td>
      <td><button class="btn dan xs" onclick="delId('${esc(a.uid)}')">Delete</button></td></tr>`).join('')
    : emptyRow(7,'No IDs yet','Add an account from the Add ID tab');

  if(ME){ ME.used = accs.length; if(ME.slots!=null){ ME.left = Math.max(0, ME.slots-accs.length); updSlots(); } }
}
function emptyRow(cols,t,sub){
  return `<tr><td colspan="${cols}" class="empty">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><path d="M8.5 14.5a4.5 4.5 0 0 0 7 0" stroke-linecap="round"/><circle cx="9" cy="9.5" r=".9" fill="currentColor"/><circle cx="15" cy="9.5" r=".9" fill="currentColor"/></svg>
    <b>${t}</b>${sub}</td></tr>`;
}
async function delId(uid){
  if(!uid || !confirm('Delete this ID? The slot will be freed.')) return;
  try{ await api('/api/account/delete',{uid}); toast('ID deleted'); loadStats(); }
  catch(e){ toast(e.message,1); }
}

/* ════════ add single ID ════════ */
$('aGo').addEventListener('click', async function(){
  const uid=$('aUid').value.trim(), password=$('aPwd').value.trim(), name=$('aName').value.trim(), m=$('aMsg');
  if(!uid||!password){ m.className='msg err'; m.textContent='Please enter both UID and password'; return; }
  if(ME && ME.left!=null && ME.left<1){ m.className='msg err'; m.textContent='Slot shesh / expire — Buy Slots theke 24h slot kino'; return; }
  const b=this, old=b.textContent; b.disabled=true; b.textContent='Adding…';
  try{
    await api('/api/account/add', {type:'guest', uid, password, name, region:'BD'});
    m.className='msg ok'; m.textContent='ID added — bot is starting';
    $('aUid').value=''; $('aPwd').value=''; $('aName').value='';
    await loadStats();
    setTimeout(()=>go('dash'), 700);
  }catch(e){ m.className='msg err'; m.textContent=e.message; }
  finally{ b.disabled=false; b.textContent=old; }
});

/* ════════ admin ════════ */
function admTab(t){
  $('atU').classList.toggle('on', t==='u'); $('atO').classList.toggle('on', t==='o');
  $('atC').classList.toggle('on', t==='c');
  $('admU').style.display = t==='u'?'block':'none';
  $('admO').style.display = t==='o'?'block':'none';
  $('admC').style.display = t==='c'?'block':'none';
  if(t==='c') loadAdmCodes();
}
async function loadAdmUsers(){
  let d; try{ d = await api('/api/panel/admin/users'); }catch(e){ return; }
  const us = d.users||[];
  $('admUsers').innerHTML = us.length ? us.map(u=>`<tr>
      <td><div class="pcell"><div class="pav">${esc(ini(u.username))}</div><div class="pnm">${esc(u.username)}</div></div></td>
      <td style="color:#00f0a8;font-weight:850;font-size:14px">${u.slots}</td>
      <td>${u.used}</td>
      <td>${expText(u.expires_at)}</td>
      <td><div class="slotctl">
        <input class="inp" id="as_${esc(u.username)}" value="5" inputmode="numeric">
        <button class="btn xs pri" onclick="admSlot('add_slots','${esc(u.username)}')">+</button>
        <button class="btn xs" onclick="admSlot('set_slots','${esc(u.username)}')">set</button>
      </div></td>
      <td><button class="btn dan xs" onclick="admDel('${esc(u.username)}')">Del</button></td></tr>`).join('')
    : emptyRow(6,'No users yet','Registered users will appear here');
}
function admSlot(action, username){
  const n = parseInt(($('as_'+username)||{}).value||'0',10)||0;
  if(!n) return toast('Enter a slot number',1);
  api('/api/panel/admin/user',{action,username,slots:n})
    .then(d=>{toast(username+' → '+d.slots+' slots · 24h'); loadAdmUsers();})
    .catch(e=>toast(e.message,1));
}
function admDel(u){ if(!confirm('User '+u+' delete?')) return;
  api('/api/panel/admin/user',{action:'delete',username:u}).then(()=>{toast('User deleted');loadAdmUsers()}).catch(e=>toast(e.message,1)); }
const OMAP={pending_payment:['PAYMENT PENDING','p-wait'],pending_review:['UNDER REVIEW','p-wait'],
  approved:['APPROVED','p-on'],rejected:['REJECTED','p-bad'],cancelled:['CANCELLED','p-off']};
const opill = s => { const[k,c]=OMAP[s]||[s,'p-off']; return `<span class="pill ${c}">${k}</span>`; };
async function loadAdmOrders(){
  let d; try{ d = await api('/api/panel/orders'); }catch(e){ return; }
  const os = d.orders||[];
  $('admOrders').innerHTML = os.length ? os.map(o=>`<tr>
      <td class="mono">${o.id}</td>
      <td><b>${esc(o.username)}</b></td>
      <td>${o.slots} slots · <span style="color:#ffd479">24h</span></td>
      <td style="color:#00f0a8;font-weight:850">₹${o.amount}</td>
      <td>${opill(o.status)}</td>
      <td style="white-space:nowrap">
        ${o.status!=='approved'?`<button class="btn pri xs" onclick="admOrd('approve','${o.id}')">Approve</button>`:''}
        ${(o.status==='pending_review'||o.status==='pending_payment')?`<button class="btn xs" onclick="admOrd('reject','${o.id}')">Reject</button>`:''}
      </td></tr>`).join('')
    : emptyRow(6,'No orders yet','New orders will appear here');
}
/* ════════ redeem codes (admin only) ════════ */
async function loadAdmCodes(){
  let d; try{ d = await api('/api/panel/admin/codes'); }catch(e){ return; }
  const cs = d.codes||[];
  $('cCount').textContent = cs.length + (cs.length===1?' code':' codes');
  $('admCodes').innerHTML = cs.length ? cs.map(c=>{
    const usedTxt = c.used + (c.limit? ' / '+c.limit : ' / ∞');
    return `<tr>
      <td><b style="font-family:ui-monospace,monospace;color:#00f0a8;letter-spacing:.8px">${esc(c.code)}</b>${c.label?`<div style="font-size:11px;color:#5b6780;margin-top:3px">${esc(c.label)}</div>`:''}</td>
      <td style="font-weight:850">+${c.slots} slots<div style="font-size:11px;color:#5b6780;font-weight:600;margin-top:2px">${c.hours}h validity</div></td>
      <td>${usedTxt}</td>
      <td style="color:#9df7d3;font-weight:750">${c.hours}h</td>
      <td>${c.active?'<span class="pill p-on">ACTIVE</span>':'<span class="pill p-off">OFF</span>'}</td>
      <td style="white-space:nowrap">
        <button class="btn xs" onclick="cdCopy('${esc(c.code)}')">Copy</button>
        <button class="btn xs" onclick="cdToggle('${esc(c.code)}')">${c.active?'Disable':'Enable'}</button>
        <button class="btn xs" onclick="cdReset('${esc(c.code)}')">Reset</button>
        <button class="btn xs dan" onclick="cdDel('${esc(c.code)}')">Del</button>
      </td></tr>`;
  }).join('') : '<tr><td colspan="6" style="padding:30px;text-align:center;color:#5b6780">No redeem codes yet — generate one above</td></tr>';
}
async function cdCreate(){
  const m = $('cMsg');
  const body = {action:'create', code:($('cCode').value||'').trim().toUpperCase(),
                auto:(($('cCode').value||'').trim()===''),
                prefix:($('cPrefix').value||'CHINNU').trim().toUpperCase(),
                slots:Number($('cSlots').value||0), hours:Number($('cHours').value||24),
                limit:Number($('cLimit').value||0), label:($('cLabel').value||'').trim()};
  if(!body.slots){ m.className='msg err'; m.textContent='Enter how many slots to give (min 1)'; return; }
  try{
    const d = await api('/api/panel/admin/codes', body);
    m.className='msg ok';
    m.textContent='Code ready: '+d.code_obj.code+' → +'+d.code_obj.slots+' slots / '+d.code_obj.hours+'h';
    $('cCode').value=''; $('cSlots').value=''; $('cHours').value=''; $('cLimit').value=''; $('cLabel').value='';
    loadAdmCodes();
    navigator.clipboard?.writeText(d.code_obj.code).catch(()=>{});
  }catch(e){ m.className='msg err'; m.textContent=e.message; }
}
function cdCopy(code){ navigator.clipboard?.writeText(code).then(()=>toast(code+' copied')).catch(()=>{}); }
function cdToggle(code){ api('/api/panel/admin/codes',{action:'toggle',code}).then(()=>loadAdmCodes()).catch(e=>toast(e.message,1)); }
function cdReset(code){ api('/api/panel/admin/codes',{action:'reset',code}).then(()=>{toast(code+' usage reset');loadAdmCodes()}).catch(e=>toast(e.message,1)); }
function cdDel(code){ if(confirm('Delete code '+code+'?')) api('/api/panel/admin/codes',{action:'delete',code}).then(()=>{toast('Deleted');loadAdmCodes()}).catch(e=>toast(e.message,1)); }
$('cGo').addEventListener('click', cdCreate);

function admOrd(action, oid){
  api('/api/panel/admin/order',{action,order_id:oid}).then(d=>{
    toast(oid+' → '+d.order.status+(d.user_slots!=null?(' · user slots '+d.user_slots):''));
    loadAdmOrders();
  }).catch(e=>toast(e.message,1));
}

boot();
setInterval(()=>{ if(ME && document.querySelector('#v-dash.on')) loadStats(); }, 8000);
</script>
</body>
</html>
'''


async def serve_page(request: web.Request):
    et = '"' + hashlib.md5(PAGE.encode()).hexdigest()[:16] + '"'
    if request.headers.get("If-None-Match") == et:
        return web.Response(status=304, headers={"ETag": et})
    return web.Response(text=PAGE, content_type="text/html", charset="utf-8",
                        headers={"ETag": et, "Cache-Control": "no-cache"})


async def healthz(request: web.Request):
    return web.Response(text="ok")


@web.middleware
async def gzip_mw(request, handler):
    resp = await handler(request)
    if isinstance(resp, web.Response) and resp.status != 304 and "Content-Encoding" not in resp.headers:
        try:
            resp.enable_compression()
        except Exception:
            pass
    return resp


def make_app() -> web.Application:
    _ensure()
    app = web.Application(middlewares=[gzip_mw])
    app.router.add_get("/", serve_page)
    app.router.add_get("/login", serve_page)
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/api/panel/me", api_me)
    app.router.add_post("/api/panel/login", api_login)
    app.router.add_post("/api/panel/register", api_register)
    app.router.add_post("/api/panel/logout", api_logout)
    app.router.add_get("/api/panel/orders", api_orders)
    app.router.add_post("/api/panel/order/create", api_order_create)
    app.router.add_post("/api/panel/redeem", api_redeem)
    app.router.add_get("/api/panel/admin/codes", api_admin_codes)
    app.router.add_post("/api/panel/admin/codes", api_admin_codes)
    app.router.add_get("/api/panel/admin/users", api_admin_users)
    app.router.add_post("/api/panel/admin/user", api_admin_user)
    app.router.add_post("/api/panel/admin/order", api_admin_order)
    app.router.add_get("/api/stats", api_stats)
    app.router.add_post("/api/account/add", api_account_add)
    app.router.add_post("/api/account/delete", api_account_delete)
    return app


if __name__ == "__main__":
    print(f"CHINNU LEVEL PRO → http://{HOST}:{PORT}")
    print(f"data dir: {BASE_DIR}")
    web.run_app(make_app(), host=HOST, port=PORT, access_log=None)
