# Code/aws_utils.py
import boto3
import os
from botocore.exceptions import ClientError

class AWSManager:
    def __init__(self, bucket_name, region_name='ap-northeast-1'):
        # 需在環境變數或 ~/.aws/credentials 中設定 AWS_ACCESS_KEY_ID 與 AWS_SECRET_ACCESS_KEY
        self.s3_client = boto3.client('s3', region_name=region_name)
        self.bucket_name = bucket_name

    def upload_file(self, local_file_path, s3_object_name=None):
        """將本地檔案上傳至 AWS S3"""
        if s3_object_name is None:
            s3_object_name = os.path.basename(local_file_path)
            
        try:
            self.s3_client.upload_file(local_file_path, self.bucket_name, s3_object_name)
            return f"s3://{self.bucket_name}/{s3_object_name}"
        except ClientError as e:
            print(f"S3 上傳失敗: {e}")
            return None

    def generate_presigned_url(self, s3_object_name, expiration=3600):
        """產生供使用者下載的臨時 URL"""
        try:
            response = self.s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': self.bucket_name,
                                                            'Key': s3_object_name},
                                                    ExpiresIn=expiration)
            return response
        except ClientError as e:
            print(f"無法產生 URL: {e}")
            return None