import argparse
import os
import time
from datetime import datetime
from json import load

import requests


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(CURRENT_DIR, "users.json")
DEFAULT_REMOTE_URL = os.getenv("REMOTE_UPDATE_URL", "https://tsg36.soc.srcf.net/update-queens-menu")


def _load_json(path, default):
    try:
        with open(path) as f:
            return load(f)
    except (FileNotFoundError, ValueError):
        return default


def _get_first_unexpired_user(users_data):
    now = datetime.now()
    for user_id, payload in users_data.items():
        expires_at_raw = payload.get("expires_at")
        access_token = payload.get("access_token")
        if not expires_at_raw or not access_token:
            continue
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
        except ValueError:
            continue
        if expires_at > now:
            return user_id, access_token, expires_at
    return None, None, None


def _pick_user(users_data, requested_user_id=None, override_token=None):
    if requested_user_id:
        user_payload = users_data.get(requested_user_id, {})
        token = override_token or user_payload.get("access_token")
        expires_at_raw = user_payload.get("expires_at")
        if not token or not expires_at_raw:
            return None, None, None
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
        except ValueError:
            return None, None, None
        if expires_at <= datetime.now():
            return None, None, None
        return requested_user_id, token, expires_at

    if override_token:
        user_id, _, expires_at = _get_first_unexpired_user(users_data)
        if not user_id:
            return None, None, None
        return user_id, override_token, expires_at

    return _get_first_unexpired_user(users_data)


def _collect_menu():
    from .get_menu_playwright import MenuScraper

    menu_scraper = MenuScraper(
        "https://www.queens.cam.ac.uk/life-at-queens/catering/cafeteria/cafeteria-menu",
        headless=True,
    )
    menu_week = menu_scraper.get_queens_week()
    menu = menu_scraper.get_queens_menu()

    if menu_week is None:
        raise RuntimeError("Failed to fetch menu week")
    if not menu:
        raise RuntimeError("Failed to fetch menu")

    return menu_week, menu


def _send_update(remote_url, user_id, access_token, menu_week, menu, mode):
    payload = {
        "user_id": user_id,
        "access_token": access_token,
        "menu_week": menu_week.isoformat(),
        "menu": menu,
        "mode": mode,
    }
    response = requests.post(remote_url, json=payload, timeout=40)
    return response.status_code, response.text


def _run_once(args):
    users_data = _load_json(args.users_file, {})
    user_id, access_token, expires_at = _pick_user(users_data, args.user_id, args.access_token)

    if not user_id or not access_token:
        print("No valid user token found. Check users.json or pass --user-id/--access-token.")
        return 1

    if expires_at:
        print(f"Using user_id={user_id}, token_expires_at={expires_at.isoformat()}")
    else:
        print(f"Using user_id={user_id}")

    try:
        menu_week, menu = _collect_menu()
    except Exception as exc:
        print(f"Menu scrape failed: {exc}")
        return 1

    try:
        status_code, text = _send_update(
            remote_url=args.remote_url,
            user_id=user_id,
            access_token=access_token,
            menu_week=menu_week,
            menu=menu,
            mode=args.mode,
        )
    except requests.RequestException as exc:
        print(f"Remote update request failed: {exc}")
        return 1

    print(f"Remote response status={status_code}")
    print(text)
    return 0 if 200 <= status_code < 300 else 1


def main():
    parser = argparse.ArgumentParser(
        description="Scrape menu locally (Playwright) and push updates to SRCF server."
    )
    parser.add_argument("--mode", choices=["auto", "daily", "weekly"], default="auto")
    parser.add_argument("--once", action="store_true", help="Run one cycle only")
    parser.add_argument("--interval-minutes", type=int, default=15)
    parser.add_argument("--remote-url", default=DEFAULT_REMOTE_URL)
    parser.add_argument("--users-file", default=USERS_FILE)
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--access-token", default=None)

    args = parser.parse_args()

    if args.interval_minutes < 1:
        parser.error("--interval-minutes must be >= 1")

    if args.once:
        raise SystemExit(_run_once(args))

    print(
        f"Starting remote updater: mode={args.mode}, every {args.interval_minutes} minutes, "
        f"remote={args.remote_url}"
    )
    while True:
        code = _run_once(args)
        if code != 0:
            print("Cycle failed; retrying next interval")
        time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    main()
