"""
REAL ENGINE BRIDGE — Garena Free Fire (OB55)
============================================
Replaces the simulated `_tick_account()` with real Garena protocol calls:

  UID + Password
      -> OAuth guest token grant        (100067.connect.garena.com)
      -> MajorLogin (AES-encrypted pb)  (loginbp.*.com)
      -> GetLoginData (pb)              -> account_id, token, aes key/iv,
                                            nickname, level, exp, region,
                                            functional_addrs, informational_addrs

Everything here is read-only against Garena: we authenticate and read the
account profile. We do NOT send match-join packets, so no game is played and
no rule is broken on our side beyond automating the login.

The heavy lifting lives in `engine/app.py` (unmodified vendor engine). We import
it lazily so the panel still boots when the engine folder is absent.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any, Dict, Optional, Tuple

ENGINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine")

_ENGINE = None
_IMPORT_ERROR: Optional[str] = None
_IMPORT_TRIED = False
_LOCK: Optional[asyncio.Lock] = None
_CLIENT = None

# Cached live release/client version from Garena's version service.
_VERSION_CACHE: Optional[Tuple[str, str, str]] = None
_VERSION_CACHE_TIME = 0.0
_VERSION_TTL = 1800.0


def engine_available() -> bool:
    """True when the vendor engine imported successfully."""
    _ensure_import()
    return _ENGINE is not None


def engine_error() -> Optional[str]:
    _ensure_import()
    return _IMPORT_ERROR


def _ensure_import() -> None:
    global _ENGINE, _IMPORT_ERROR, _IMPORT_TRIED
    if _IMPORT_TRIED:
        return
    _IMPORT_TRYED = True  # noqa: F841  (kept for clarity)
    _IMPORT_TRIED = True
    if not os.path.isdir(ENGINE_DIR):
        _IMPORT_ERROR = "engine folder missing"
        return
    if ENGINE_DIR not in sys.path:
        sys.path.insert(0, ENGINE_DIR)
    try:
        import app as engine  # type: ignore
        _ENGINE = engine
        _IMPORT_ERROR = None
    except Exception as exc:  # pragma: no cover - depends on env
        _ENGINE = None
        _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


def _get_lock() -> asyncio.Lock:
    global _LOCK
    if _LOCK is None:
        _LOCK = asyncio.Lock()
    return _LOCK


async def _get_client():
    """The vendor engine keeps an httpx client in module global `client`."""
    global _CLIENT
    _ensure_import()
    if _ENGINE is None:
        return None
    if _CLIENT is None:
        import httpx
        _CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=20.0),
            follow_redirects=True,
            headers={
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B Build/SP1A.210812.016)",
                "Accept-Encoding": "gzip, deflate",
            },
        )
        # the engine reads the module global directly
        _ENGINE.client = _CLIENT
    return _CLIENT


async def live_version() -> Tuple[str, str, str]:
    """(release_version, client_version, login_base_url) straight from Garena."""
    global _VERSION_CACHE, _VERSION_CACHE_TIME
    now = time.time()
    if _VERSION_CACHE and (now - _VERSION_CACHE_TIME) < _VERSION_TTL:
        return _VERSION_CACHE
    await _get_client()
    _ensure_import()
    if _ENGINE is None:
        raise RuntimeError(_IMPORT_ERROR or "engine unavailable")
    cfg = await asyncio.wait_for(_ENGINE.version_config(), timeout=60)
    if not cfg:
        raise RuntimeError("Garena version service returned nothing")
    _VERSION_CACHE = cfg
    _VERSION_CACHE_TIME = now
    return cfg


def _pick(obj: Any, *names: str, default=None):
    """Works on protobuf messages and plain dicts alike."""
    for n in names:
        try:
            if isinstance(obj, dict):
                if n in obj:
                    return obj[n]
            else:
                v = getattr(obj, n)
                if v not in (None, "", 0) or n == names[-1]:
                    return v
        except Exception:
            continue
    return default


def _extract_profile(res_proto: Any, dict_res: Dict[str, Any]) -> Dict[str, Any]:
    """Pull nickname / level / exp / region out of the GetLoginData response."""
    prof: Dict[str, Any] = {}
    src = dict_res or {}

    # protobuf decoder output is a flat-ish dict; search a few common spellings
    flat: Dict[str, Any] = {}

    def _walk(node, depth=0):
        if depth > 4 or not isinstance(node, dict):
            return
        for k, v in node.items():
            lk = str(k).lower()
            if lk in ("nickname", "name", "accountname", "playername", "ign"):
                flat.setdefault("nickname", v)
            elif lk in ("level", "accountlevel", "lvl"):
                flat.setdefault("level", v)
            elif lk in ("exp", "experience", "totalexp", "expcount"):
                flat.setdefault("exp", v)
            elif lk in ("region", "regionname"):
                flat.setdefault("region", v)
            elif lk in ("likes", "liked", "total_likes"):
                flat.setdefault("likes", v)
            if isinstance(v, dict):
                _walk(v, depth + 1)

    _walk(src)

    for msg in (res_proto, getattr(res_proto, "basic_info", None), getattr(res_proto, "account_info", None)):
        if msg is None:
            continue
        for attr in ("nickname", "account_name", "name", "level", "exp", "region", "likes"):
            try:
                v = getattr(msg, attr)
                if v not in (None, "", 0):
                    prof.setdefault(attr, v)
            except Exception:
                pass

    for k, v in flat.items():
        prof.setdefault(k, v)

    clean: Dict[str, Any] = {}
    try:
        nick = prof.get("nickname") or prof.get("account_name") or prof.get("name")
        if nick:
            clean["nickname"] = str(nick)[:32]
    except Exception:
        pass
    for key in ("level", "exp", "likes"):
        try:
            if key in prof and prof[key] is not None:
                clean[key] = int(prof[key])
        except Exception:
            pass
    if prof.get("region"):
        clean["region"] = str(prof["region"])[:8]
    return clean


async def real_login(uid: str, password: str) -> Dict[str, Any]:
    """
    Perform a genuine Garena login for one account.

    Returns a dict:
      ok=True  -> {ok, nickname, level, exp, region, account_id, token, ...}
      ok=False -> {ok, error, code}
    """
    uid = str(uid).strip()
    password = str(password or "").strip()
    if not uid or not password:
        return {"ok": False, "error": "UID and password are required", "code": "bad_input"}

    _ensure_import()
    if _ENGINE is None:
        return {"ok": False, "error": f"engine not available ({_IMPORT_ERROR})", "code": "no_engine"}

    async with _get_lock():
        try:
            await _get_client()
        except Exception as exc:
            return {"ok": False, "error": f"network setup failed: {exc}", "code": "network"}

        try:
            release_version, client_version, server_url = await live_version()
        except Exception as exc:
            return {"ok": False, "error": f"Garena version service unreachable: {exc}", "code": "version"}

        # ---- 1. OAuth guest token -------------------------------------------
        try:
            tok = await asyncio.wait_for(_ENGINE.get_access_token(uid, password), timeout=60)
        except asyncio.TimeoutError:
            return {"ok": False, "error": "Garena login timed out", "code": "timeout"}
        except Exception as exc:
            return {"ok": False, "error": f"login error: {exc}", "code": "login"}

        if tok is None:
            return {"ok": False,
                    "error": "Garena rejected the login — wrong UID/password, or this server IP is rate-limited",
                    "code": "auth_failed"}
        if tok == "BANNED":
            return {"ok": False, "error": "This account is banned by Garena", "code": "banned"}

        try:
            open_id, access_token, platform = tok
        except Exception:
            return {"ok": False, "error": "unexpected OAuth response", "code": "login"}

        # ---- 2. MajorLogin (AES + protobuf) ---------------------------------
        try:
            device_info = _ENGINE.get_device_for_account(uid)
            payload = await _ENGINE.build_majorlogin_payload(
                open_id, access_token, platform, client_version, device_info
            )
            if payload is None:
                return {"ok": False, "error": "could not build the login packet", "code": "payload"}
            major = await asyncio.wait_for(
                _ENGINE.send_majorlogin(payload, release_version, server_url), timeout=60
            )
        except asyncio.TimeoutError:
            return {"ok": False, "error": "Garena login server timed out", "code": "timeout"}
        except Exception as exc:
            return {"ok": False, "error": f"login packet failed: {exc}", "code": "majorlogin"}

        if major is None:
            return {"ok": False, "error": "Garena login server did not answer", "code": "majorlogin"}
        if major == "BANNED":
            return {"ok": False, "error": "This account is banned by Garena", "code": "banned"}

        # ---- 3. GetLoginData -> profile + session ---------------------------
        try:
            got = await asyncio.wait_for(
                _ENGINE.send_getlogin(payload, major.url, major.token, release_version), timeout=60
            )
        except asyncio.TimeoutError:
            return {"ok": False, "error": "profile request timed out", "code": "timeout"}
        except Exception as exc:
            return {"ok": False, "error": f"profile request failed: {exc}", "code": "getlogin"}

        if not got:
            return {"ok": False, "error": "Garena returned no profile data", "code": "getlogin"}

        res_proto, dict_res = got
        profile = _extract_profile(res_proto, dict_res)

        out: Dict[str, Any] = {
            "ok": True,
            "uid": uid,
            "account_id": str(_pick(res_proto, "account_id", default=uid) or uid),
            "nickname": profile.get("nickname") or f"Player_{uid[-4:]}",
            "level": int(profile.get("level") or 1),
            "exp": int(profile.get("exp") or 0),
            "likes": int(profile.get("likes") or 0),
            "region": (profile.get("region") or "IND")[:8],
            "release_version": release_version,
            "client_version": client_version,
            "live": True,
        }
        # session material the engine would need to keep the account online
        for k_attr, k_out in (
            ("functional_addrs", "functional_addrs"),
            ("informational_addrs", "informational_addrs"),
        ):
            try:
                out[k_out] = list(getattr(res_proto, k_attr))
            except Exception:
                out[k_out] = []
        return out


def real_login_sync(uid: str, password: str) -> Dict[str, Any]:
    """Blocking wrapper for places that are not async (tests, CLI)."""
    return asyncio.run(real_login(uid, password))


if __name__ == "__main__":
    import json
    if len(sys.argv) < 3:
        print("usage: python real_engine.py <uid> <password>")
        raise SystemExit(2)
    print(json.dumps(real_login_sync(sys.argv[1], sys.argv[2]), indent=2, ensure_ascii=False))
