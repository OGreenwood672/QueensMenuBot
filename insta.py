import requests

class InstagramAPI:
    def __init__(self):
        self.access_token = "YOUR_INSTAGRAM_ACCESS_TOKEN"
        self.user_id = "YOUR_INSTAGRAM_USER_ID"
        self.api_url = f"https://graph.instagram.com/{self.user_id}/media"

    def post_images(self, images, caption):
        # Save the images locally first
        image_urls = []
        for i, img in enumerate(images):
            img_path = f"menu_day_{i}.png"
            img.save(img_path)
            image_urls.append(self.upload_image(img_path))

        # Create a post with all images
        post_data = {
            'image_urls': image_urls,
            'caption': caption,
            'access_token': self.access_token
        }

        response = requests.post(f"{self.api_url}/create", data=post_data)
        return response.json()

    def post_story(self, image, caption):
        # Save the image locally
        img_path = "daily_menu.png"
        image.save(img_path)
        media_id = self.upload_image(img_path)

        # Post the image as a story
        post_data = {
            'media_id': media_id,
            'access_token': self.access_token,
            'caption': caption
        }

        response = requests.post(f"{self.api_url}/create_story", data=post_data)
        return response.json()

    def upload_image(self, img_path):
        # Upload image to Instagram
        files = {
            'file': open(img_path, 'rb'),
        }
        response = requests.post(f"{self.api_url}/upload", files=files, data={
            'access_token': self.access_token
        })
        return response.json()['id']
