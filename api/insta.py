import requests


class InstagramAPI:

    FB_API_URL = 'https://graph.facebook.com/v20.0'

    def __init__(self, user_id, access_token):
        self.user_id = user_id
        self.access_token = access_token
    
    def validate_code(self, code, app_id, app_secret, redirect_uri):
        url = f"{self.FB_API_URL}/oauth/access_token"
        params = {
            'client_id': app_id,
            'client_secret': app_secret,
            'code': code,
            'redirect_uri': redirect_uri
        }
        response = requests.get(url, params=params)
        return response.json()


    def get_long_lived_token(self, short_lived_token, app_id, app_secret):
        url = f"{self.FB_API_URL}/oauth/access_token"
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': app_id,
            'client_secret': app_secret,
            'fb_exchange_token': short_lived_token,
        }

        response = requests.get(url, params=params)
        print("RESPONSE", response.json())
        return response.json()


    def get_instagram_account_id(self):
        url = f"{self.FB_API_URL}/me/accounts?access_token={self.access_token}"
        response = requests.get(url)
        data = response.json()
        print("DATA", data)
        if 'data' in data and len(data['data']) > 0:

            page_id = data['data'][0]['id']  # Assume first page is the correct one
            instagram_url = f"{self.FB_API_URL}/{page_id}?fields=instagram_business_account&access_token={self.access_token}"
            response = requests.get(instagram_url)
            print(response.json())
            return response.json().get('id', None)

        return None


    def create_instagram_media_object(self, image_url, caption):

        url = f"{self.FB_API_URL}/{self.user_id}/media"

        params = {
            'image_url': image_url,
            'caption': caption,
            'access_token': self.access_token
        }

        response = requests.post(url, data=params)
        print(response.json())
        return response.json().get('id')

    def publish_instagram_post(self, media_object_id):

        url = f"{self.FB_API_URL}/{self.user_id}/media_publish"
        params = {
            'creation_id': media_object_id,
            'access_token': self.access_token
        }

        response = requests.post(url, data=params)
        return response.json()

    def create_carousel_container(self, media_ids):
        url = f"{self.FB_API_URL}/{self.user_id}/media"
        params = {
            'media_type': 'CAROUSEL',
            'children': ','.join(media_ids),
            'access_token': self.access_token
        }
        response = requests.post(url, data=params)
        return response.json().get('id')

    def post_carousel(self, imgs, caption=""):
        # Step 1: Create media objects for each image
        media_ids = []
        for img in imgs:
            media_id = self.create_instagram_media_object(img, "")
            if media_id:
                media_ids.append(media_id)

        if not media_ids:
            raise ValueError("No media objects were created successfully.")

        # Step 2: Create a carousel container
        carousel_id = self.create_carousel_container(media_ids)
        if not carousel_id:
            raise ValueError("Failed to create carousel container.")

        # Step 3: Publish the carousel post
        result = self.publish_instagram_post(carousel_id)
        return result