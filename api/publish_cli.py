import argparse
import mimetypes
import os
import time
from contextlib import suppress
from datetime import datetime, timedelta
from json import load, dump
from uuid import uuid4

import requests


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(CURRENT_DIR, "users.json")
CUSTOM_DETAILS_FILE = os.path.join(CURRENT_DIR, "custom_details.json")
POST_HISTORY_FILE = os.path.join(CURRENT_DIR, "posts_made.json")
EPOCH_ISO = "1970-01-01T00:00:00"
DEFAULT_MENU_URL = "https://www.queens.cam.ac.uk/life-at-queens/catering/cafeteria/cafeteria-menu"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
VERIFY_RETRIES = 5
VERIFY_RETRY_SECONDS = 1


def _load_json(path, default):
    try:
        with open(path) as f:
            return load(f)
    except (FileNotFoundError, ValueError):
        return default


def _save_json(path, data):
    with open(path, "w") as f:
        dump(data, f)


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


def _ensure_user_custom_state(custom_data, user_id):
    state = custom_data.setdefault(user_id, {})
    state.setdefault("current_day", EPOCH_ISO)
    state.setdefault("current_week", EPOCH_ISO)
    return state


def _today_floor_iso():
    return datetime.today().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _today_date_iso():
    return datetime.today().date().isoformat()


def _default_post_history():
    return {"daily": [], "weekly": []}


def _load_post_history():
    raw = _load_json(POST_HISTORY_FILE, _default_post_history())
    if not isinstance(raw, dict):
        return _default_post_history()

    daily = raw.get("daily", [])
    weekly = raw.get("weekly", [])

    if not isinstance(daily, list):
        daily = []
    if not isinstance(weekly, list):
        weekly = []

    # Keep insertion order while removing duplicates and non-strings.
    normalized_daily = list(dict.fromkeys(value for value in daily if isinstance(value, str)))
    normalized_weekly = list(dict.fromkeys(value for value in weekly if isinstance(value, str)))
    return {"daily": normalized_daily, "weekly": normalized_weekly}


def _has_daily_post(post_history, day_iso):
    return day_iso in post_history["daily"]


def _has_weekly_post(post_history, week_start_iso):
    return week_start_iso in post_history["weekly"]


def _record_daily_post(post_history, day_iso):
    if not _has_daily_post(post_history, day_iso):
        post_history["daily"].append(day_iso)


def _record_weekly_post(post_history, week_start_iso):
    if not _has_weekly_post(post_history, week_start_iso):
        post_history["weekly"].append(week_start_iso)


def _new_run_id():
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ") + f"-{uuid4().hex[:8]}"


def _format_week_caption(menu_week):
    return f"Week Commencing {menu_week.strftime('%d/%m/%y')}"


def _upload_temp_image(r2, local_path, run_id):
    ext = os.path.splitext(local_path)[1].lower() or ".jpg"
    object_key = f"tmp/{run_id}/{uuid4().hex}{ext}"
    content_type = mimetypes.guess_type(local_path)[0] or "image/jpeg"
    public_url = r2.upload_file(local_path, object_key, content_type=content_type)
    _verify_uploaded_image(public_url)
    print(f"Uploaded image: {public_url}")
    return public_url, object_key


def _verify_uploaded_image(public_url):
    last_error = None
    for _ in range(VERIFY_RETRIES):
        try:
            response = requests.get(public_url, timeout=15)
            if response.status_code >= 400:
                last_error = f"HTTP {response.status_code}"
            else:
                content_type = (response.headers.get("Content-Type") or "").lower()
                if "image/" in content_type:
                    return
                last_error = f"unexpected content-type: {content_type or '<missing>'}"
        except requests.RequestException as exc:
            last_error = str(exc)

        time.sleep(VERIFY_RETRY_SECONDS)

    raise RuntimeError(f"Uploaded image is not publicly reachable: {public_url} ({last_error})")


def _upload_menu_json(r2, menu_week, menu):
    generated_at = datetime.utcnow().isoformat() + "Z"
    week_start = menu_week.date().isoformat()
    payload = {
        "generated_at": generated_at,
        "week_commencing": week_start,
        "source": DEFAULT_MENU_URL,
        "menu": menu,
    }

    latest_url = r2.upload_json(payload, f"api/menu/latest.json")
    week_url = r2.upload_json(payload, f"api/menu/week-{week_start}.json")
    return latest_url, week_url


def _cleanup_enabled():
    return os.getenv("CLOUDFLARE_DELETE_TEMP_AFTER_POST", "false").strip().lower() in {"1", "true", "yes"}


def _cleanup_temp_images(r2, keys):
    if not _cleanup_enabled():
        print("Temporary image cleanup skipped (set CLOUDFLARE_DELETE_TEMP_AFTER_POST=true to enable).")
        return
    with suppress(Exception):
        r2.delete_keys(keys)


def _post_weekly_via_cloudflare(api, pg, r2, menu_week, menu):
    run_id = _new_run_id()
    temp_keys, media_urls = [], []
    for index, day in enumerate(WEEKDAYS):
        day_date = menu_week + timedelta(days=index)
        local_path = pg.generate_image(day, day_date.strftime("%d %B"), menu.get(day, {}))
        public_url, object_key = _upload_temp_image(r2, local_path, run_id)
        media_urls.append(public_url)
        temp_keys.append(object_key)

    result = api.post_carousel(media_urls, _format_week_caption(menu_week))
    _cleanup_temp_images(r2, temp_keys)
    return result


def _post_daily_via_cloudflare(api, pg, r2, menu):
    run_id = _new_run_id()
    temp_keys = []
    day = datetime.today().strftime("%A")
    local_path = pg.generate_story(day, datetime.now().strftime("%d %B"), menu.get(day, {}))
    public_url, object_key = _upload_temp_image(r2, local_path, run_id)
    temp_keys.append(object_key)

    media_object_id = api.create_instagram_media_object(public_url, "Today's Menu", is_story=True)
    result = api.publish_instagram_post(media_object_id)
    _cleanup_temp_images(r2, temp_keys)
    return result


def _run_once(mode):
    try:
        from .cloudflare_r2 import CloudflareR2Client
        from .get_menu_playwright import MenuScraper
        from .insta import InstagramAPI
        from .make_post import PostGenerator
    except ModuleNotFoundError as exc:
        print(f"Missing dependency: {exc}. Install required packages before running publish cycles.")
        return 1

    users_data = _load_json(USERS_FILE, {})
    user_id, access_token, expires_at = _get_first_unexpired_user(users_data)

    if not user_id:
        print("No unexpired user token found in users.json")
        return 1

    print(f"Using user_id={user_id}, token_expires_at={expires_at.isoformat()}")

    custom_data = _load_json(CUSTOM_DETAILS_FILE, {})
    state = _ensure_user_custom_state(custom_data, user_id)
    post_history = _load_post_history()

    api = InstagramAPI(user_id=user_id, access_token=access_token)
    r2 = CloudflareR2Client()
    menu_scraper = MenuScraper(DEFAULT_MENU_URL, headless=True)

    menu_week = menu_scraper.get_queens_week()
    if menu_week is None:
        print("Failed to fetch menu week")
        return 1

    menu = menu_scraper.get_queens_menu()
    if not menu:
        print("Failed to fetch menu")
        return 1

    latest_menu_url, week_menu_url = _upload_menu_json(r2, menu_week, menu)
    print(f"Published menu JSON: latest={latest_menu_url}")
    print(f"Published menu JSON: weekly={week_menu_url}")

    pg = PostGenerator(base_url="")

    posted_weekly, posted_daily = False, False
    today_floor = _today_floor_iso()
    today_date = _today_date_iso()
    week_start_date = menu_week.date().isoformat()

    if mode == "weekly":
        if _has_weekly_post(post_history, week_start_date):
            print(f"Skipping weekly post: already posted for week commencing {week_start_date}")
        else:
            _post_weekly_via_cloudflare(api, pg, r2, menu_week, menu)
            state["current_week"] = menu_week.isoformat()
            _record_weekly_post(post_history, week_start_date)
            _save_json(POST_HISTORY_FILE, post_history)
            posted_weekly = True

    elif mode == "daily":
        if _has_daily_post(post_history, today_date):
            print(f"Skipping daily post: already posted for {today_date}")
        else:
            _post_daily_via_cloudflare(api, pg, r2, menu)
            state["current_day"] = today_floor
            _record_daily_post(post_history, today_date)
            _save_json(POST_HISTORY_FILE, post_history)
            posted_daily = True

    else:  # auto
        if not _has_weekly_post(post_history, week_start_date):
            _post_weekly_via_cloudflare(api, pg, r2, menu_week, menu)
            state["current_week"] = menu_week.isoformat()
            _record_weekly_post(post_history, week_start_date)
            _save_json(POST_HISTORY_FILE, post_history)
            posted_weekly = True
        else:
            print(f"Skipping weekly post: already posted for week commencing {week_start_date}")

        if (
            datetime.now() > menu_week
            and datetime.now() < menu_week + timedelta(days=7)
            and not _has_daily_post(post_history, today_date)
            and datetime.now().time() > datetime.strptime("05:59", "%H:%M").time()
        ):
            _post_daily_via_cloudflare(api, pg, r2, menu)
            state["current_day"] = today_floor
            _record_daily_post(post_history, today_date)
            _save_json(POST_HISTORY_FILE, post_history)
            posted_daily = True
        elif _has_daily_post(post_history, today_date):
            print(f"Skipping daily post: already posted for {today_date}")

    _save_json(CUSTOM_DETAILS_FILE, custom_data)
    _save_json(POST_HISTORY_FILE, post_history)
    print(f"Done. posted_weekly={posted_weekly}, posted_daily={posted_daily}, mode={mode}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Queens Menu Bot CLI publisher via Cloudflare R2")
    parser.add_argument(
        "--mode",
        choices=["auto", "daily", "weekly"],
        default="auto",
        help="auto = only when needed; daily = force today's story now; weekly = force this week's full post now",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one cycle only",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=15,
        help="Polling interval in minutes for continuous mode",
    )
    args = parser.parse_args()

    if args.interval_minutes < 1:
        parser.error("--interval-minutes must be >= 1")

    if args.once:
        raise SystemExit(_run_once(args.mode))

    print(f"Starting continuous publisher: mode={args.mode}, every {args.interval_minutes} minutes")
    while True:
        code = _run_once(args.mode)
        if code != 0:
            print("Cycle failed; retrying next interval")
        time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    main()
