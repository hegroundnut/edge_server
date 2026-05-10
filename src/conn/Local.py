import oss2
import yaml
import os
import sys
import shutil
import hashlib
from pathlib import Path

from src.util.log import setup_custom_logger

logger = setup_custom_logger('LOCALDISK')

# 通过local_root_path指定一个本地的磁盘（类似oss 的bucket的概念）
class CLocalDisk(object):

    def __init__(self, disk_root_path):
        self.disk_root_path = disk_root_path

    def getRemoteFileHash(self, remote_file):
        """
        获取本地文件的MD5哈希值
        @param remote_file: 本地文件路径
        @return: 文件MD5哈希值（小写）或None
        """
        remote_path = self.disk_root_path + remote_file
        if not os.path.exists(remote_path):
            # logger.error(f"文件不存在: {remote_path}")
            return None

        hash_md5 = hashlib.md5()
        try:
            with open(remote_path, "rb") as f:
                # 分块读取大文件
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            # 返回小写MD5值，与Minio的ETag格式保持一致
            return hash_md5.hexdigest().lower()
        except Exception as e:
            logger.error(f"计算本地文件hash失败: {str(e)}")
            return None

    # 本地文件拷贝
    def downloadFile(self, remote_path, local_path):
        """
        本地文件拷贝（为了和云存储统一，downloadfile是把第三方文件目录的文件拷贝到本地
        @remote_path 
        """
        remote_path = self.disk_root_path + remote_path
        self.priv_copyFile(remote_path,local_path)


    def uploadFile(self, remote_path, local_path):
        """
        上传文件到
        """
        remote_path = self.disk_root_path + remote_path
        self.priv_copyFile(local_path,remote_path)
    
    def deleteFile(self,remote_path):
        """
        删除文件
        """
        remote_path = self.disk_root_path + remote_path
        os.remove(remote_path)
    

    # 在同一个bucket中移动目录
    def moveDirectory(self, src_dir, dst_dir):
        """
        将 MinIO 中指定目录下的所有对象移动到另一个目录。

        :param src_dir :源目录 DsDataCollection / CSKIN人脸 / wrinkle
        :param dst_dir :目标目录，如：DsDataCollection / CSKIN人脸2 / wrinkle
        """
        pass
    
    # 在同一个bucket中移动文件
    def moveFile(self, src_file, dst_file):
        """
        将 MinIO 中指定文件移动到目标文件位置。

        :param src_file: 源文件路径
        :param dst_file: 目标文件路径
        """
        pass
    
    # 根据Storage的copyFile在本地DISK中拷贝
    def copyFile(self, src_file, dst_file):
        """
        本地文件拷贝，支持自动创建目标目录并保留文件元数据

        :param src_file: 源文件路径（绝对路径或相对路径）
        :type src_file: str
        :param dst_file: 目标文件路径（绝对路径或相对路径）
        :type dst_file: str
        :raises FileNotFoundError: 源文件不存在时抛出
        :raises PermissionError: 无读写权限时抛出
        :raises IsADirectoryError: 当src_file是目录或dst_file是已存在目录时抛出
        """
        # 验证源文件存在性
        if not os.path.isfile(src_file):
            raise FileNotFoundError(f"源文件不存在: {src_file}")
        
        # 创建目标目录（如果不存在）
        dst_dir = os.path.dirname(dst_file)
        if dst_dir and not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
        
        # 执行文件拷贝（保留元数据）
        shutil.copy2(src_file, dst_file)
        
        # 验证拷贝结果
        if not os.path.exists(dst_file):
            raise RuntimeError(f"文件拷贝失败: {src_file} -> {dst_file}")

    # 私有函数，实现本地文件（绝对路径）拷贝
    def priv_copyFile(self, src_file, dst_file):
        """
        本地文件拷贝，支持自动创建目标目录并保留文件元数据

        :param src_file: 源文件路径（绝对路径或相对路径）
        :type src_file: str
        :param dst_file: 目标文件路径（绝对路径或相对路径）
        :type dst_file: str
        :raises FileNotFoundError: 源文件不存在时抛出
        :raises PermissionError: 无读写权限时抛出
        :raises IsADirectoryError: 当src_file是目录或dst_file是已存在目录时抛出
        """
        # 验证源文件存在性
        if not os.path.isfile(src_file):
            raise FileNotFoundError(f"源文件不存在: {src_file}")
        
        # 创建目标目录（如果不存在）
        dst_dir = os.path.dirname(dst_file)
        if dst_dir and not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
        
        # 执行文件拷贝（保留元数据）
        shutil.copy2(src_file, dst_file)
        
        # 验证拷贝结果
        if not os.path.exists(dst_file):
            raise RuntimeError(f"文件拷贝失败: {src_file} -> {dst_file}")
        

    
    def listFiles(self, dir):
        """
        @param dir: 目标目录, 如： AIDataManage / CskinAlgoCollect / FaceDectation
        @return 
        [{
            ftype:D/F,
            name:'xxxx.jpg'
        }]
        """
        dir = self.disk_root_path + dir.strip('/')
        file_list = []
        
        # 检查目录是否存在
        if not os.path.isdir(dir):
            return file_list
            
        # 仅列出当前目录下的文件和目录
        for entry in os.listdir(dir):
            entry_path = os.path.join(dir, entry)
            if os.path.isfile(entry_path):
                file_list.append({
                    'ftype': 'F',
                    'name': entry
                })
            elif os.path.isdir(entry_path):
                file_list.append({
                    'ftype': 'D',
                    'name': entry
                })
        
        return file_list
    
    # 检测minio中某个指定的文件是否存在
    def checkFileExist(self,file):
        """
        @param file :指定的文件
        @return 
        {
            'exist':True, #文件是否存在
        }
        """
        pass
    
    # 统计目录下的文件数量
    def getFileNum(self,dir):
        """
        @param dir :指定的目录
        @return 
        {
            'dnum':3434, #目录的数量
            'fnum':33 # 文件的数量
        }
        """
        pass
