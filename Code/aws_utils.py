# Code/aws_utils.py
import boto3
import os
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

class AWSManager:
    def __init__(self):
        # boto3 會自動從環境變數讀取 AWS_ACCESS_KEY_ID 與 AWS_SECRET_ACCESS_KEY
        self.bucket_name = os.getenv("AWS_BUCKET_NAME")
        self.region = os.getenv("AWS_REGION", "ap-northeast-1")
        
        self.s3_client = boto3.client(
            's3', 
            region_name=self.region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )

    def upload_file(self, local_file_path, object_name=None):
        """將本地檔案上傳至 AWS S3"""
        if object_name is None:
            object_name = os.path.basename(local_file_path)
            
        try:
            self.s3_client.upload_file(local_file_path, self.bucket_name, object_name)
            return True
        except ClientError as e:
            print(f"S3 上傳失敗: {e}")
            return False

    def get_download_url(self, object_name, expiration=3600):
        """產生預先簽名的下載 URL"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            print(f"無法產生 URL: {e}")
            return None