import oss2
import yaml
import os
import sys
import hashlib
from minio import Minio
# from minio.datatypes import CopySource
from minio.commonconfig import CopySource

from minio.error import S3Error
from src.util.log import setup_custom_logger

logger = setup_custom_logger('MINIO')


class CMinioManager(object):

    def __init__(self, access_key, secret_key, bucket_name, end_point):
        self.ACCESS_KEY = access_key
        self.SECRET_KEY = secret_key
        self.END_POINT = end_point
        self.bucket_name = bucket_name

        self.minio_client = Minio(
            end_point,
            access_key=access_key,
            secret_key=secret_key,
            secure=False
        )

    # 获取云存储指定文件的hash值
    def getRemoteFileHash(self,remote_file):
        """
        @param remote_file: 目标文件
        @return:
        """
        hash_value = None
        try:
            response = self.minio_client.stat_object(self.bucket_name, remote_file)
            hash_value = response.etag
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.error("目标文件不存在")
        except Exception as e:
            logger.error(e)
        return hash_value

    # 获取本地文件的hash值
    def getLocalFileHash(self, local_file):
        """
        获取本地文件的MD5哈希值，与Minio的ETag对应
        @param local_file: 本地文件路径
        @return: 文件MD5哈希值（小写）或None
        """
        if not os.path.exists(local_file):
            logger.error(f"文件不存在: {local_file}")
            return None

        hash_md5 = hashlib.md5()
        try:
            with open(local_file, "rb") as f:
                # 分块读取大文件
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            # 返回小写MD5值，与Minio的ETag格式保持一致
            return hash_md5.hexdigest().lower()
        except Exception as e:
            logger.error(f"计算本地文件hash失败: {str(e)}")
            return None
    
    # 比较本地文件和远程文件的hash是否相同
    def compareFileHash(self,local_file,remote_file):
        """
        比较本地文件和远程文件的MD5哈希值是否相同
        @param local_file: 本地文件路径
        @param remote_file: 远程文件路径
        @return: True如果哈希值相同，False否则
        """
        local_hash = self.getLocalFileHash(local_file)
        remote_hash = self.getRemoteFileHash(remote_file)

        if local_hash and remote_hash:
            return local_hash == remote_hash
        else:
            return False

    def downloadFile(self, remote_path, local_path):
        """
        从mino上下载文件
        """
        try:
            logger.info("Downloading {} to {}".format(
                remote_path,
                local_path
            ))
            self.minio_client.fget_object(self.bucket_name, remote_path, local_path)
            return 1
        except (oss2.exceptions.ClientError, oss2.exceptions.NoSuchKey) as e:
            logger.error(e)
            return 0


    def uploadFile(self, remote_path, local_path):
        """
        上传文件到OSS/Minio
        """
        try:
            logger.info("Uploading {} to {}".format(
                local_path,
                remote_path
            ))
            self.minio_client.fput_object(self.bucket_name, remote_path, local_path)
            return 1
        except (oss2.exceptions.ClientError, oss2.exceptions.NoSuchKey) as e:
            logger.error(e)
            return 0

    def deleteFile(self, remote_file):
        """
        删除文件
        """
        try:
            self.minio_client.remove_object(self.bucket_name, remote_file)
            return 1
        except (oss2.exceptions.ClientError, oss2.exceptions.NoSuchKey) as e:
            logger.error(e)
            return 0

    # 在同一个bucket中移动目录
    def moveDirectory(self, src_dir, dst_dir):
        """
        将 MinIO 中指定目录下的所有对象移动到另一个目录。

        :param src_dir :源目录 DsDataCollection / CSKIN人脸 / wrinkle
        :param dst_dir :目标目录，如：DsDataCollection / CSKIN人脸2 / wrinkle
        """
        try:
            # 确保源目录和目标目录以斜杠结尾
            if not src_dir.endswith('/'):
                src_dir += '/'
            if not dst_dir.endswith('/'):
                dst_dir += '/'
            
            # 列出源目录中的所有对象
            objects = self.minio_client.list_objects(self.bucket_name, prefix=src_dir, recursive=True)
            
            for obj in objects:
                # 获取对象的完整路径
                object_name = obj.object_name
                # 构造目标路径
                target_object_name = object_name.replace(src_dir, dst_dir, 1)
                
                # 复制对象到目标路径
                self.minio_client.copy_object(
                    self.bucket_name,
                    target_object_name,
                    f"{self.bucket_name}/{object_name}"
                )
                
                # 删除源对象
                self.minio_client.remove_object(self.bucket_name, object_name)
            
            print(f"成功将目录 {src_dir} 移动到 {dst_dir}")
        
        except S3Error as e:
            print(f"发生错误: {e}")
    
    # 在同一个bucket中移动文件
    def moveFile(self, src_file, dst_file):
        """
        将 MinIO 中指定文件移动到目标文件位置。

        :param src_file: 源文件路径
        :param dst_file: 目标文件路径
        """
        print(f"源文件路径: {src_file}, 目标文件路径: {dst_file}")
        try:
            # 创建 CopySource 对象
            copy_source = CopySource(self.bucket_name, src_file)
            
            # 复制文件到目标路径
            self.minio_client.copy_object(
                self.bucket_name,
                dst_file,
                copy_source
            )
            
            # 删除源文件
            self.minio_client.remove_object(self.bucket_name, src_file)
            
            print(f"成功将文件 {src_file} 移动到 {dst_file}")
        
        except S3Error as e:
            print(f"发生错误: {e}")
    
    # 添加文件复制方法
    def copyFile(self, src_file, dst_file):
        """
        复制文件到目标路径，保留源文件
        :param src_file: 源文件路径
        :param dst_file: 目标文件路径
        """
        try:
            copy_source = CopySource(self.bucket_name, src_file)
            self.minio_client.copy_object(
                self.bucket_name,
                dst_file,
                copy_source
            )
            print(f"成功复制文件: {src_file} -> {dst_file}")
            return True
        except S3Error as e:
            print(f"复制文件失败: {e}")
            return False
    
    def listFiles(self,dir):
        """
        @param dir: 目标目录, 如： AIDataManage / CskinAlgoCollect / FaceDectation
        @return 
        [{
            ftype:D/F,
            name:'xxxx.jpg'
        }]
        """
        result = []
        try:
            # 列出指定目录下的所有对象
            objects = self.minio_client.list_objects(self.bucket_name, prefix=dir.strip("/")+"/", recursive=False)
            
            for obj in objects:
                entry_info = {
                    'ftype': 'D' if obj.is_dir else 'F',
                    'name': os.path.basename(os.path.dirname(obj.object_name)) if obj.is_dir else os.path.basename(obj.object_name)
                }
                result.append(entry_info)
            # 按照文件名称排序
            result.sort(key=lambda x: x['name'])
        except S3Error as e:
            print(f"发生错误: {e}")
        
        return result
    
    def getFileNum(self,dir):
        """
        @param dir :指定的目录
        @return 
        {
            'dnum':3434, #目录的数量
            'fnum':33 # 文件的数量
        }
        """
        result = {
            'dnum':0, #目录的数量
            'fnum':0 # 文件的数量
        }
        try:
            # 列出指定目录下的所有对象
            objects = self.minio_client.list_objects(self.bucket_name, prefix=dir.strip("/")+"/", recursive=False)
            
            for obj in objects:
                if obj.is_dir :
                    result['dnum'] = result['dnum'] + 1
                else :
                    result['fnum'] = result['fnum'] + 1
        except S3Error as e:
            print(f"发生错误: {e}")
        
        return result
