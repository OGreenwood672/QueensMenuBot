import argparse
import os
from datetime import datetime
from json import load

import requests


GRAPH_API_VERSION = "v24.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
REQUIRED_TASKS = {"CREATE_CONTENT", "MANAGE"}
DEFAULT_PAGE_ID = "361949037011803"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(CURRENT_DIR, "users.json")


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


def fetch_accounts(access_token: str) -> dict:
    url = f"{GRAPH_BASE_URL}/me/accounts"
    params = {
        "fields": "instagram_business_account,name,tasks",
        "access_token": access_token,
    }
    response = requests.get(url, params=params, timeout=20)
    return response.json()


def fetch_page_instagram_business_account(page_id: str, access_token: str) -> dict:
    url = f"{GRAPH_BASE_URL}/{page_id}"
    params = {
        "fields": "instagram_business_account",
        "access_token": access_token,
    }
    response = requests.get(url, params=params, timeout=20)
    return response.json()


def has_authority(payload: dict) -> bool:
    pages = payload.get("data", [])
    print(pages)

    found_authority = False
    for page in pages:
        name = page.get("name", "<unknown>")
        tasks = set(page.get("tasks", []))
        instagram_account = page.get("instagram_business_account") or {}
        instagram_id = instagram_account.get("id")

        has_required_task = bool(tasks & REQUIRED_TASKS)
        has_instagram_link = bool(instagram_id)

        print(f"Page: {name}")
        print(f"  tasks: {sorted(tasks) if tasks else []}")
        print(f"  instagram_business_account: {instagram_id}")
        print(f"  authority_ok: {has_required_task and has_instagram_link}")

        if has_required_task and has_instagram_link:
            found_authority = True

    return found_authority


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether the access token can see Page tasks and linked "
            "instagram_business_account via /me/accounts."
        )
    )
    parser.add_argument(
        "--access-token",
        default=None,
        help="Facebook user access token (overrides users.json lookup)",
    )
    parser.add_argument(
        "--page-id",
        default=DEFAULT_PAGE_ID,
        help="Page ID for direct instagram_business_account check",
    )

    args = parser.parse_args()
    access_token = args.access_token

    if not access_token:
        users_data = _load_json(USERS_FILE, {})
        user_id, access_token, expires_at = _get_first_unexpired_user(users_data)
        if not access_token:
            print("No unexpired user token found in users.json. Pass --access-token to override.")
            return 1
        print(f"Using user_id={user_id}, token_expires_at={expires_at.isoformat()}")

    payload = fetch_accounts(access_token)

    if "error" in payload:
        print("Graph API error:")
        print(payload["error"])
        return 1

    if not payload.get("data"):
        print("No pages returned. Token may not have the required permissions.")
        return 1

    page_payload = fetch_page_instagram_business_account(args.page_id, access_token)
    print(page_payload)
    print(f"\nDirect page check: /{args.page_id}?fields=instagram_business_account")
    if "error" in page_payload:
        print("Graph API error (direct page check):")
        print(page_payload["error"])
    else:
        direct_ig = (page_payload.get("instagram_business_account") or {}).get("id")
        print(f"  instagram_business_account: {direct_ig}")

    ok = has_authority(payload)
    direct_ok = bool((page_payload.get("instagram_business_account") or {}).get("id")) if "error" not in page_payload else False

    if ok and direct_ok:
        print("\nResult: authority check passed.")
        return 0

    print("\nResult: authority check failed (missing me/accounts authority and/or direct page instagram_business_account link).")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
