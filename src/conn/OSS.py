"""Aliyun OSS server operation file
"""
from itertools import count
import oss2
import yaml
import os
import sys
from os import mkdir
from src.util.log import setup_custom_logger

logger = setup_custom_logger('OSS')


class OSSManager(object):

    def __init__(self, access_id, secret_secret, bucket_name, end_point):
        self.ALIYUN_ACCESS_KEY_ID = access_id
        self.ALIYUN_ACCESS_KEY_SECRET = secret_secret
        self.auth = oss2.Auth(self.ALIYUN_ACCESS_KEY_ID, self.ALIYUN_ACCESS_KEY_SECRET)
        self.end_point = end_point
        self.bucket_name = bucket_name

    def downloadFile(self, remote_path, local_path):
        """
        从OSS上下载文件
        """
        try:
            logger.info("Downloading {} to {}".format(
                remote_path,
                local_path
            ))
            oss2.Bucket(self.auth, self.end_point, self.bucket_name).get_object_to_file(remote_path, local_path)
            return 1
        except (oss2.exceptions.ClientError, oss2.exceptions.NoSuchKey) as e:
            logger.error(e)
            return 0

    def uploadFile(self, remote_path, local_path):
        """
        上传文件到OSS
        """
        try:
            logger.info("Uploading {} to {}".format(
                remote_path,
                local_path
            ))
            oss2.Bucket(self.auth, self.end_point, self.bucket_name).put_object_from_file(remote_path, local_path)
            return 1
        except (oss2.exceptions.ClientError, oss2.exceptions.NoSuchKey) as e:
            logger.error(e)
            return 0


   