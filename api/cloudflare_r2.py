import json
import os
from typing import Iterable

import boto3
from dotenv import load_dotenv


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".env"))
load_dotenv(ENV_PATH)


class CloudflareR2Client:
    REQUIRED_ENV = {
        "CLOUDFLARE_ACCOUNT_ID": "account_id",
        "CLOUDFLARE_R2_ACCESS_KEY_ID": "access_key_id",
        "CLOUDFLARE_R2_SECRET_ACCESS_KEY": "secret_access_key",
        "CLOUDFLARE_R2_BUCKET": "bucket",
        "CLOUDFLARE_R2_PUBLIC_BASE_URL": "public_base_url",
    }

    def __init__(self):
        self.account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        self.access_key_id = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID")
        self.secret_access_key = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
        self.bucket = os.getenv("CLOUDFLARE_R2_BUCKET")
        self.public_base_url = (os.getenv("CLOUDFLARE_R2_PUBLIC_BASE_URL") or "").rstrip("/")
        self.key_prefix = (os.getenv("CLOUDFLARE_R2_PREFIX") or "queens-menu-bot").strip("/")

        missing = [name for name, attr in self.REQUIRED_ENV.items() if not getattr(self, attr)]
        if missing:
            raise ValueError(f"Missing Cloudflare config: {', '.join(missing)}")

        endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto",
        )

    def _full_key(self, key: str) -> str:
        normalized = key.strip("/")
        if self.key_prefix:
            return f"{self.key_prefix}/{normalized}"
        return normalized

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{self._full_key(key)}"

    def upload_file(self, local_path: str, key: str, content_type: str = "application/octet-stream") -> str:
        full_key = self._full_key(key)
        with open(local_path, "rb") as f:
            self.client.put_object(
                Bucket=self.bucket,
                Key=full_key,
                Body=f,
                ContentType=content_type,
                CacheControl="public, max-age=300",
            )
        return self.public_url(key)

    def upload_json(self, payload: dict, key: str) -> str:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        full_key = self._full_key(key)
        self.client.put_object(
            Bucket=self.bucket,
            Key=full_key,
            Body=body,
            ContentType="application/json",
            CacheControl="public, max-age=60",
        )
        return self.public_url(key)

    def delete_keys(self, keys: Iterable[str]):
        objects = [{"Key": self._full_key(k)} for k in keys if k]
        if not objects:
            return

        # R2 supports S3-compatible delete_objects
        self.client.delete_objects(
            Bucket=self.bucket,
            Delete={"Objects": objects, "Quiet": True},
        )
