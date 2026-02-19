from flask import Flask, redirect, request, Request, jsonify
from .insta import InstagramAPI
from .make_post import PostGenerator
from datetime import timedelta, datetime
from dotenv import load_dotenv
import os
from json import load, dump
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_cors import CORS


current_dir = os.path.dirname(os.path.abspath(__file__))
users_file = os.path.join(current_dir, 'users.json')
custom_details_file = os.path.join(current_dir, 'custom_details.json')
EPOCH_ISO = "1970-01-01T00:00:00"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


env_path = os.path.abspath(os.path.join(current_dir, "..", ".env"))
load_dotenv(env_path)

FB_APP_ID = os.getenv("FB_APP_ID")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
OAUTH_BASE_URL = os.getenv("OAUTH_BASE_URL", "http://localhost:5000").rstrip("/")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://tsg36.soc.srcf.net").rstrip("/")
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("PORT", "5000"))
REDIRECT_URI_CODE = f'{OAUTH_BASE_URL}/validate-code'
REDIRECT_URI_VALID_CODE = f'{OAUTH_BASE_URL}/callback'

class R(Request):
    trusted_hosts = {"tsg36.soc.srcf.net", "webserver.srcf.societies.cam.ac.uk", "localhost", "127.0.0.1"}
 

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'
app.request_class = R
app.wsgi_app = ProxyFix(app.wsgi_app)


def _load_json(path, default):
    try:
        with open(path) as f:
            return load(f)
    except (FileNotFoundError, ValueError):
        return default


def _save_json(path, payload):
    with open(path, "w") as f:
        dump(payload, f)


def _ensure_user_custom_state(user_id):
    data = _load_json(custom_details_file, {})
    state = data.setdefault(user_id, {})
    state.setdefault("current_day", EPOCH_ISO)
    state.setdefault("current_week", EPOCH_ISO)
    _save_json(custom_details_file, data)
    return state


def _today_floor_iso():
    return datetime.today().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _is_update_authorized(user_id, provided_token):
    if not user_id or not provided_token:
        return False, "Missing user_id or access_token"

    token_data = get_user(user_id)
    if not token_data:
        return False, "Unknown user_id"

    if token_data["expires_at"] <= datetime.now():
        return False, "Stored token is expired"

    if token_data["access_token"] != provided_token:
        return False, "Token mismatch"

    return True, None


def _post_weekly(api, pg, menu_week, menu):
    menu_names = []
    for index, day in enumerate(WEEKDAYS):
        day_date = menu_week + timedelta(days=index)
        menu_names.append(pg.generate_image(day, day_date.strftime("%d %B"), menu.get(day, {})))
    api.post_carousel(menu_names)


def _post_daily(api, pg, menu):
    day = datetime.today().strftime("%A")
    img = pg.generate_story(day, datetime.now().strftime("%d %B"), menu.get(day, {}))
    media_object_id = api.create_instagram_media_object(img, "Today's Menu", is_story=True)
    api.publish_instagram_post(media_object_id)


def save_user(user_id, token, expiration_time):
    print("SAVING", user_id)
    data = _load_json(users_file, {})

    data.setdefault(user_id, {})
    data[user_id]['access_token'] = token
    data[user_id]['expires_at'] = (datetime.now() + timedelta(seconds=expiration_time)).isoformat()

    _save_json(users_file, data)


def get_user(user_id):
    user = _load_json(users_file, {}).get(user_id)
    if user:
        user['expires_at'] = datetime.fromisoformat(user['expires_at'])
    return user
    
def get_user_custom_details(user_id):
    return _load_json(custom_details_file, {}).get(user_id)

def save_user_custom_details(user_id, details):
    data = _load_json(custom_details_file, {})
    data[user_id] = details
    _save_json(custom_details_file, data)

def is_token_expiring_soon(expiration_time):
    time_left = expiration_time - datetime.now()
    return time_left.days <= 5  # Refresh if token expires within 5 days


def refresh_token_if_needed(user_id):
    token_data = get_user(user_id)
    if not token_data:
        return None

    access_token = token_data['access_token']
    expiration_time = token_data['expires_at']
    if is_token_expiring_soon(expiration_time):
        api = InstagramAPI(user_id, access_token)
        long_lived_token_data = api.get_long_lived_token(access_token, FB_APP_ID, FB_APP_SECRET)

        if 'access_token' in long_lived_token_data:
            new_token = long_lived_token_data['access_token']
            save_user(user_id, new_token, long_lived_token_data.get('expires_in', 3600 * 24 * 30))
            return new_token

    return access_token

@app.route('/')
def index():
    fb_login_url = f"https://www.facebook.com/v24.0/dialog/oauth?client_id={FB_APP_ID}&redirect_uri={REDIRECT_URI_CODE}&scope=instagram_content_publish,instagram_basic,pages_read_engagement,pages_show_list,business_management"
    return redirect(fb_login_url)

@app.route('/validate-code')
def validate_code():
    code = request.args.get("code")
    print(f"got code: {code}")
    if code:
        api = InstagramAPI(None, None)

        response = api.validate_code(code, FB_APP_ID, FB_APP_SECRET, REDIRECT_URI_CODE)

        print(f"validation {response}, {FB_APP_ID}, {REDIRECT_URI_CODE}")

        if 'access_token' in response:
            return redirect(REDIRECT_URI_VALID_CODE + f"?access_token={response['access_token']}")
    
    return 'Invalid Code', 404

@app.route('/callback')
def callback():
    access_token = request.args.get('access_token')
    if access_token:

        api = InstagramAPI(None, None)
        token_response = api.get_long_lived_token(access_token, FB_APP_ID, FB_APP_SECRET)
        if 'access_token' in token_response:

            api.access_token = token_response['access_token']
            user_id = api.get_instagram_account_id()
            if user_id == None:
                return 'No Connected Instagram Account Found'

            save_user(
                user_id,
                token_response['access_token'],
                token_response.get('expires_in', 3600 * 24 * 30)
            )

            return 'Success', 200

    return 'Authorization failed', 400

@app.route("/update-queens-menu", methods=["GET", "POST"])
def update_menu():
    if request.method == "GET":
        return jsonify(
            {
                "message": "Use POST with JSON: user_id, access_token, menu_week (ISO), menu, mode",
                "example_mode_values": ["auto", "daily", "weekly"],
            }
        ), 200

    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    provided_token = payload.get("access_token")
    menu = payload.get("menu")
    menu_week_raw = payload.get("menu_week")
    mode = payload.get("mode", "auto")

    if mode not in {"auto", "daily", "weekly"}:
        return jsonify({"error": "Invalid mode"}), 400

    if not isinstance(menu, dict) or not menu_week_raw:
        return jsonify({"error": "Missing/invalid menu or menu_week"}), 400

    try:
        menu_week = datetime.fromisoformat(menu_week_raw)
    except ValueError:
        return jsonify({"error": "menu_week must be ISO format"}), 400

    authorized, reason = _is_update_authorized(user_id, provided_token)
    if not authorized:
        return jsonify({"error": f"Unauthorized: {reason}"}), 403

    access_token = refresh_token_if_needed(user_id)
    if not access_token:
        return jsonify({"error": "User not found"}), 404

    user_custom_details = _ensure_user_custom_state(user_id)
    api = InstagramAPI(user_id=user_id, access_token=access_token)
    pg = PostGenerator(base_url=PUBLIC_BASE_URL)

    posted_weekly, posted_daily = False, False
    today_floor = _today_floor_iso()

    if mode == "weekly":
        _post_weekly(api, pg, menu_week, menu)
        user_custom_details["current_week"] = menu_week.isoformat()
        posted_weekly = True
    elif mode == "daily":
        _post_daily(api, pg, menu)
        user_custom_details["current_day"] = today_floor
        posted_daily = True
    else:
        if datetime.fromisoformat(user_custom_details["current_week"]) != menu_week:
            _post_weekly(api, pg, menu_week, menu)
            user_custom_details["current_week"] = menu_week.isoformat()
            posted_weekly = True

        if (
            datetime.now() > menu_week
            and datetime.now() < menu_week + timedelta(days=7)
            and datetime.fromisoformat(user_custom_details["current_day"]) != datetime.fromisoformat(today_floor)
            and datetime.now().time() > datetime.strptime("05:59", "%H:%M").time()
        ):
            _post_daily(api, pg, menu)
            user_custom_details["current_day"] = today_floor
            posted_daily = True

    save_user_custom_details(user_id, user_custom_details)

    return jsonify(
        {
            "ok": True,
            "mode": mode,
            "posted_weekly": posted_weekly,
            "posted_daily": posted_daily,
            "user_id": user_id,
        }
    ), 200


if __name__ == '__main__':
    app.run(debug=True, host=APP_HOST, port=APP_PORT)

