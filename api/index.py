from flask import Flask, redirect, request, Request
from .insta import InstagramAPI
from .get_menu import MenuScraper
from .make_post import PostGenerator
from datetime import timedelta, datetime
from dotenv import load_dotenv
import os
from json import load, dump
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage


current_dir = os.path.dirname(os.path.abspath(__file__))
users_file = os.path.join(current_dir, 'users.json')
custom_details_file = os.path.join(current_dir, 'custom_details.json')
service_key = os.path.join(current_dir, 'queens-menu-bot-firebase-adminsdk-atuxv-7cf94de0e7.json')


load_dotenv(".env")

FB_APP_ID = os.getenv("FB_APP_ID")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
HOST = os.getenv("HOST")
REDIRECT_URI_CODE = f'{HOST}validate-code'
REDIRECT_URI_VALID_CODE = f'{HOST}callback'
STORAGE = os.getenv("STORAGE")


cred = credentials.Certificate(service_key)
firebase_admin.initialize_app(cred, {
    'storageBucket': STORAGE
})

class R(Request):
    trusted_hosts = {"qjcr.soc.srcf.net", "webserver.srcf.societies.cam.ac.uk"}

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'
app.request_class = R
app.wsgi_app = ProxyFix(app.wsgi_app)


def save_user(user_id, token, expiration_time):
    print("SAVING", user_id)
    with open(users_file) as f:
        data = load(f)
    
    if data.get(user_id) == None:
        data[user_id] = {}

    data[user_id]['access_token'] = token
    data[user_id]['expires_at'] = (datetime.now() + timedelta(seconds=expiration_time)).isoformat()

    with open(users_file, "w") as f:
        dump(data, f)


def get_user(user_id):
    with open(users_file) as f:
        user = load(f).get(user_id)
        if user:
            user['expires_at'] = datetime.fromisoformat(user['expires_at'])
        return user
    
def get_user_custom_details(user_id):
    with open(custom_details_file) as f:
        return load(f).get(user_id)

def save_user_custom_details(user_id, details):
    with open(custom_details_file) as f:
        data = load(f)
    data[user_id] = details
    with open(custom_details_file, "w") as f:
        dump(data, f)

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
    fb_login_url = f"https://www.facebook.com/v20.0/dialog/oauth?client_id={FB_APP_ID}&redirect_uri={REDIRECT_URI_CODE}&scope=instagram_content_publish,instagram_basic,pages_read_engagement,pages_show_list,business_management"
    return redirect(fb_login_url)

@app.route('/validate-code')
def validate_code():
    code = request.args.get("code")
    if code:
        api = InstagramAPI(None, None)
        response = api.validate_code(code, FB_APP_ID, FB_APP_SECRET, REDIRECT_URI_CODE)

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

@app.route("/update-queens-menu")
def update_menu():
    user_id = request.args.get("user_id")
    access_token = refresh_token_if_needed(user_id)
    user_custom_details = get_user_custom_details(user_id)

    if access_token:
        api = InstagramAPI(user_id=user_id, access_token=access_token)
        menu_scraper = MenuScraper("https://www.queens.cam.ac.uk/life-at-queens/catering/cafeteria/cafeteria-menu")

        bucket = storage.bucket()
        blobs = bucket.list_blobs()
        for blob in blobs:
            blob.delete()

        menu_week = menu_scraper.get_queens_week()
        if datetime.fromisoformat(user_custom_details['current_week']) != menu_week:
            user_custom_details['current_week'] = menu_week.isoformat()
            print("Posting Weekly")
            menu = menu_scraper.get_queens_menu()
            pg = PostGenerator()
            menu_names = []
            for index, day in enumerate(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']):
                day_date = menu_week + timedelta(days=index)
                menu_names.append(pg.generate_image(day, day_date.strftime("%d %B"), menu[day], storage))

            api.post_carousel(menu_names)
        
        if (
            datetime.now() > menu_week and datetime.now() < menu_week + timedelta(days=7) and
            datetime.fromisoformat(user_custom_details['current_day']) != datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) and
            datetime.now().time() > datetime.strptime("05:59", "%H:%M").time()
        ):
            user_custom_details['current_day'] = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            print("Posting Daily")
            pg = PostGenerator()
            day = datetime.today().strftime('%A')
            img = pg.generate_story(day, datetime.now().strftime("%d %B"), menu_scraper.get_queens_menu()[day], storage)
            media_object_id = api.create_instagram_media_object(img, "Today's Menu", is_story=True)
            api.publish_instagram_post(media_object_id)

        save_user_custom_details(user_id, user_custom_details)

        return 'Queens Menu Bot has updated Menu', 200

    return 'User not found', 404


if __name__ == '__main__':
    app.run(debug=True)

