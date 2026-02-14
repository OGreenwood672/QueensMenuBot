import argparse
import os
import time
from datetime import datetime, timedelta
from json import load, dump


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(CURRENT_DIR, "users.json")
CUSTOM_DETAILS_FILE = os.path.join(CURRENT_DIR, "custom_details.json")
DEFAULT_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://tsg36.soc.srcf.net").rstrip("/")


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
    if user_id not in custom_data:
        custom_data[user_id] = {
            "current_day": "1970-01-01T00:00:00",
            "current_week": "1970-01-01T00:00:00",
        }
    custom_data[user_id].setdefault("current_day", "1970-01-01T00:00:00")
    custom_data[user_id].setdefault("current_week", "1970-01-01T00:00:00")
    return custom_data[user_id]


def _post_weekly(api, pg, menu_week, menu):
    menu_names = []
    for index, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]):
        day_date = menu_week + timedelta(days=index)
        day_menu = menu.get(day, {})
        menu_names.append(pg.generate_image(day, day_date.strftime("%d %B"), day_menu))
    api.post_carousel(menu_names)


def _post_daily(api, pg, menu):
    day = datetime.today().strftime("%A")
    img = pg.generate_story(day, datetime.now().strftime("%d %B"), menu.get(day, {}))
    media_object_id = api.create_instagram_media_object(img, "Today's Menu", is_story=True)
    api.publish_instagram_post(media_object_id)


def _run_once(mode, base_url):
    try:
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

    api = InstagramAPI(user_id=user_id, access_token=access_token)
    menu_scraper = MenuScraper(
        "https://www.queens.cam.ac.uk/life-at-queens/catering/cafeteria/cafeteria-menu",
        headless=True,
    )

    menu_week = menu_scraper.get_queens_week()
    if menu_week is None:
        print("Failed to fetch menu week")
        return 1

    menu = menu_scraper.get_queens_menu()
    if not menu:
        print("Failed to fetch menu")
        return 1

    pg = PostGenerator(base_url=base_url.rstrip("/"))

    posted_weekly = False
    posted_daily = False

    if mode == "weekly":
        _post_weekly(api, pg, menu_week, menu)
        state["current_week"] = menu_week.isoformat()
        posted_weekly = True

    elif mode == "daily":
        _post_daily(api, pg, menu)
        state["current_day"] = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        posted_daily = True

    else:  # auto
        if datetime.fromisoformat(state["current_week"]) != menu_week:
            _post_weekly(api, pg, menu_week, menu)
            state["current_week"] = menu_week.isoformat()
            posted_weekly = True

        if (
            datetime.now() > menu_week
            and datetime.now() < menu_week + timedelta(days=7)
            and datetime.fromisoformat(state["current_day"]) != datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
            and datetime.now().time() > datetime.strptime("05:59", "%H:%M").time()
        ):
            _post_daily(api, pg, menu)
            state["current_day"] = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            posted_daily = True

    _save_json(CUSTOM_DETAILS_FILE, custom_data)
    print(f"Done. posted_weekly={posted_weekly}, posted_daily={posted_daily}, mode={mode}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Queens Menu Bot CLI publisher")
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
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Public base URL for generated images (default: http://localhost:5000)",
    )

    args = parser.parse_args()

    if args.interval_minutes < 1:
        parser.error("--interval-minutes must be >= 1")

    if args.once:
        raise SystemExit(_run_once(args.mode, args.base_url))

    print(f"Starting continuous publisher: mode={args.mode}, every {args.interval_minutes} minutes")
    while True:
        code = _run_once(args.mode, args.base_url)
        if code != 0:
            print("Cycle failed; retrying next interval")
        time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    main()
