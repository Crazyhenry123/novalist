import json
import boto3
from app.config import settings


class S3Store:
    def __init__(self):
        self.s3 = boto3.client("s3", region_name=settings.aws_region)
        self.bucket = settings.s3_bucket

    def save_text(self, key: str, text: str):
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=text.encode("utf-8"), ContentType="text/plain; charset=utf-8")

    def load_text(self, key: str) -> str:
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read().decode("utf-8")
        except self.s3.exceptions.NoSuchKey:
            return ""

    def save_json(self, key: str, data: dict):
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=json.dumps(data, ensure_ascii=False).encode("utf-8"), ContentType="application/json")

    def load_json(self, key: str) -> dict:
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except self.s3.exceptions.NoSuchKey:
            return {}
        except Exception:
            return {}

    def list_keys(self, prefix: str) -> list[str]:
        try:
            resp = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            return [obj["Key"] for obj in resp.get("Contents", [])]
        except Exception:
            return []
