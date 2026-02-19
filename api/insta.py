import time

import requests


class InstagramAPI:

    FB_API_URL = "https://graph.facebook.com/v24.0"
    MEDIA_CREATE_RETRIES = 4
    MEDIA_CREATE_RETRY_DELAY_SECONDS = 2
    TRANSIENT_ERROR_CODES = {1, 2, 4, 17, 32, 341}

    def __init__(self, user_id, access_token):
        self.user_id = user_id
        self.access_token = access_token

    def _get(self, path, **params):
        response = requests.get(f"{self.FB_API_URL}/{path}", params=params)
        return response.json()

    def _post(self, path, **data):
        response = requests.post(f"{self.FB_API_URL}/{path}", data=data)
        return response.json()

    def validate_code(self, code, app_id, app_secret, redirect_uri):
        return self._get(
            "oauth/access_token",
            client_id=app_id,
            client_secret=app_secret,
            code=code,
            redirect_uri=redirect_uri,
        )

    def get_long_lived_token(self, short_lived_token, app_id, app_secret):
        return self._get(
            "oauth/access_token",
            grant_type="fb_exchange_token",
            client_id=app_id,
            client_secret=app_secret,
            fb_exchange_token=short_lived_token,
        )

    def get_instagram_account_id(self):
        data = self._get("me/accounts", access_token=self.access_token)
        pages = data.get("data", [])
        if pages:
            page_id = pages[0].get("id")  # Keep original behavior: first page
            if page_id:
                page_data = self._get(
                    page_id,
                    fields="instagram_business_account",
                    access_token=self.access_token,
                )
                return (page_data.get("instagram_business_account") or {}).get("id")

        return None

    def create_instagram_media_object(self, image_url, caption, is_story=False):
        if not isinstance(image_url, str) or not image_url.startswith(("http://", "https://")):
            raise ValueError(
                "image_url must be a public http(s) URL reachable by Meta Graph API"
            )

        params = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.access_token,
        }
        if is_story:
            params["media_type"] = "STORIES"

        for attempt in range(1, self.MEDIA_CREATE_RETRIES + 1):
            payload = self._post(f"{self.user_id}/media", **params)
            print(payload)

            media_id = payload.get("id")
            if media_id:
                return media_id

            error = payload.get("error", {})
            is_transient = bool(error.get("is_transient")) or error.get("code") in self.TRANSIENT_ERROR_CODES
            if attempt >= self.MEDIA_CREATE_RETRIES or not is_transient:
                return None

            print(
                f"Transient media link failure (attempt {attempt}/{self.MEDIA_CREATE_RETRIES}); retrying in "
                f"{self.MEDIA_CREATE_RETRY_DELAY_SECONDS}s"
            )
            time.sleep(self.MEDIA_CREATE_RETRY_DELAY_SECONDS)

        return None

    def publish_instagram_post(self, media_object_id):
        return self._post(
            f"{self.user_id}/media_publish",
            creation_id=media_object_id,
            access_token=self.access_token,
        )

    def create_carousel_container(self, media_ids, caption=""):
        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(media_ids),
            "access_token": self.access_token,
        }
        if caption:
            params["caption"] = caption

        payload = self._post(f"{self.user_id}/media", **params)
        return payload.get("id")

    def post_carousel(self, imgs, caption=""):
        # Step 1: Create media objects for each image
        media_ids = []
        for idx, img in enumerate(imgs, start=1):
            media_id = self.create_instagram_media_object(img, "")
            if not media_id:
                raise ValueError(f"Failed to link carousel image {idx}/{len(imgs)} after retries.")
            media_ids.append(media_id)

        if not media_ids:
            raise ValueError("No media objects were created successfully.")

        # Step 2: Create a carousel container
        carousel_id = self.create_carousel_container(media_ids, caption=caption)
        if not carousel_id:
            raise ValueError("Failed to create carousel container.")

        # Step 3: Publish the carousel post
        return self.publish_instagram_post(carousel_id)