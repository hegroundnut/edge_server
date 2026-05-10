import os
import uuid
import copy
from tqdm import tqdm
from src.util.log import setup_custom_logger
from ..conn.OSS import OSSManager
from ..conn.Minio import CMinioManager
from ..conn.Local import CLocalDisk

logger = setup_custom_logger('Storage')

# 维护多个存储连接管理
class StoragesMng(object):
    """
    @功能 维护多个存储连接管理
    @概念 remote 表示包括云存储(oss、minio)对象位置、磁盘存储(local、remotelinux)对象位子
    @概念 local  表示本地文件(一般是运行过程的本地临时目录)
    """
    def __init__(self, node_cfg, proc_modules_obj, progress_callback):
        self.node_cfg = node_cfg
        self.proc_modules_obj = proc_modules_obj
        self.progress_callback = progress_callback

        # 云存储对象，格式:
        # {
        #     'conn_name':'cskin',
        #     'conn_type':'oss/azure/minio',
        #     'storage_obj':[StorageMngObj]
        # }
        self.cloud_storage_pool = []
        # urlrequest 对象

    # 在两个存储之间同步文件（包含子目录文件）
    def syncFilesBetweenStorages(self,src_conn_name,src_path,dst_conn_name,dst_path,sync_mode):
        """
        @param  src_storage_conn_name  连接的存储名称
        @param  src_path  源路径（相对路径）
        @param  dst_storage_conn_name  连接的存储名称
        @param  dst_path  目标路径（相对路径）
        @param  sync_mode  同步模式，
                            IncSync:增量同步,同步增加、修改文件
                            FullSync:全量同步,同步增加、修改、删除文件
        """
        print('syncFilesBetweenStorages',src_path,dst_path)
        # 遍历src端的所有文件和目录
        src_file_list = self.listFiles(src_conn_name,src_path)
        # 同步该目录下的所有的文件
        # 1、获取目标目录下的所有的文件列表，并且标记已经同步的文件
        dst_file_list = []
        org_dst_file_list = self.listFiles(dst_conn_name,dst_path) #包括目录和文件
        dst_file_list = copy.deepcopy(org_dst_file_list)
        for dst_file in dst_file_list: # 把目标文件都标记成未同步
            if (dst_file['ftype'] ==  'F' ):
                dst_file['is_sync'] = False
        # 2、同步文件和目录
        pbar = tqdm(src_file_list, desc="同步图像中", ncols=80)


        for src_file in pbar:
            
            self.proc_modules_obj['imgbase'].send_progress(pbar, deal_msg = 'sycn file {}'.format(src_file))
            # 2.1 如果是目录则递归同步
            if src_file['ftype'] == 'D' : #递归同步下一层目录
                self.syncFilesBetweenStorages(src_conn_name,src_path + '/' + src_file['name'],dst_conn_name,dst_path + '/' + src_file['name'],sync_mode)
            # 2.2 如果是文件则同步文件
            elif src_file['ftype'] == 'F':
                # 2.2.1 获取源文件和目标文件的hash
                src_file_hash = self.getRemoteFileHash(src_conn_name,src_path + '/' + src_file['name'])
                dst_file_hash = self.getRemoteFileHash(dst_conn_name,dst_path + '/' + src_file['name'])
                if src_file_hash == None: # 源文件错误
                    print(f"警告: 源文件不存在 - {src_conn_name}:{src_path}/{src_file['name']}")
                    continue
                if dst_file_hash is None:
                    print(f"信息: 目标文件不存在，准备创建 - {dst_path}/{src_file['name']}")
                elif src_file_hash != dst_file_hash:
                    print(f"信息: 文件内容不匹配，准备更新 - {dst_path}/{src_file['name']}")
                elif src_file_hash == dst_file_hash :
                    print(f"信息: 文件相同,无需更新 - {dst_path}/{src_file['name']}")
                    # 标记目标文件为"已同步"
                    for dst_file in dst_file_list:
                        if (dst_file['ftype'] ==  'F' and dst_file['name'] == src_file['name']):
                            dst_file['is_sync'] = True
                    continue
                # 2.2.1 执行文件同步
                try:
                    filename_uuid = str(uuid.uuid4())
                    filename_ext = os.path.splitext(src_file['name'])[1].lstrip('.')
                    # local_filename = self.node_cfg['tmp_data'] + '/' + filename_uuid + '.' + filename_ext
                    local_filename = os.path.join(self.node_cfg['tmp_data'], f"{filename_uuid}.{filename_ext}")
                    self.downloadFile(src_conn_name,src_path + '/' + src_file['name'],local_filename)
                    self.uploadFile(dst_conn_name,local_filename,dst_path + '/' + src_file['name'])
                    print('同步：%s -> %s' % (src_path + '/' + src_file['name'],dst_path + '/' + src_file['name']))
                    os.remove(local_filename) #删除临时文件
                except:
                    print('同步文件失败:',src_path + '/' + src_file['name'],dst_path + '/' + src_file['name'])
                
                # 2.2.2 标记目标文件为"已同步"
                for dst_file in dst_file_list:
                    if (dst_file['ftype'] ==  'F' and dst_file['name'] == src_file['name']):
                        dst_file['is_sync'] = True
        # 3、删除目标目录下的所有未同步的文件
        if sync_mode == 'FullSync': #全量同步模式，删除目标目录中未被同步的数据（说明源路径中已经被删除）
            for dst_file in dst_file_list:
                if (dst_file['ftype'] ==  'F' and dst_file['is_sync'] == False):
                    self.deleteFile(dst_conn_name,dst_path + '/' + dst_file['name'])
                    print('删除：%s' % (dst_path + '/' + dst_file['name']))
                    # 如果ds_path目录下面没有文件和子目录，该目录可以被删除
                    # TODO: 待实现
                    # if self.isDirEmpty(dst_conn_name,dst_path):
                    #     self.deleteDir(dst_conn_name,dst_path)
                    #     print('删除目录：%s' % (dst_path))
                        
        elif sync_mode == 'IncSync': #增量同步数据无需处理
            pass

    def downloadFile(self,dconn_name, remote_file,local_file):
        #根据名称获取连接信息
        cloud_obj = self.priv_get_storage_byname(dconn_name)
        cloud_obj["conn_obj"].downloadFile(remote_file, local_file)

    def uploadFile(self, dconn_name, local_file,remote_file):
        #根据名称获取连接信息
        cloud_obj = self.priv_get_storage_byname(dconn_name)
        cloud_obj["conn_obj"].uploadFile(remote_file, local_file)
    
    def deleteFile(self, dconn_name, remote_file):
        #根据名称获取连接信息
        cloud_obj = self.priv_get_storage_byname(dconn_name)
        cloud_obj["conn_obj"].deleteFile(remote_file)
    
    # 获取云存储指定文件的hash值
    def getRemoteFileHash(self,conn_name,remote_file):
        """
        @param conn_name 连接的云存储名称
        @param remote_file 云存储文件路径
        @return 文件的hash值
                None 表示出错或者文件不存在
        """
        cloud_obj = self.priv_get_storage_byname(conn_name)
        return cloud_obj["conn_obj"].getRemoteFileHash(remote_file)

    # 列出指定目录dir下的所有文件和目录（仅限下一层，不要深度搜索）
    def listFiles(self,conn_name,dir):
        """
        @param dir: 目标目录, 如： AIDataManage / CskinAlgoCollect / FaceDectation
        @return 
        [{
            ftype:D/F,
            name:'xxxx.jpg'
        }]
        """
        cloud_obj = self.priv_get_storage_byname(conn_name)
        result = cloud_obj["conn_obj"].listFiles(dir)
        return result

    def priv_get_storage_byname(self,conn_name):
        print("conn_name: ", conn_name)
        #先查找该存储连接是否已经存在
        conn_obj = None
        for conn_obj in self.cloud_storage_pool:
            if (conn_obj['conn_name'] == conn_name):
                return conn_obj
        #如果没有找到该对象
        storageinfo = self.node_cfg['cloud_storage_dconn_cfg'][conn_name]
        if storageinfo != None :
            
            if "oss" == storageinfo['STORAGE_TYPE']:
                conn_obj = {
                    "conn_name":conn_name,
                    'conn_type':storageinfo['STORAGE_TYPE'], #oss/minio/azure
                    'bucket_name':storageinfo['BUCKET_NAME'],
                    "conn_obj": OSSManager(
                        storageinfo['ALIYUN_ACCESS_KEY_ID'], 
                        storageinfo['ALIYUN_ACCESS_KEY_SECRET'], 
                        storageinfo['BUCKET_NAME'], 
                        storageinfo['ALIYUN_INTERNAL_END_POINT'] # 只在阿里内网能用
                    )
                }
            elif "minio" == storageinfo['STORAGE_TYPE']:
                conn_obj = {
                    "conn_name":conn_name,
                    "conn_type":storageinfo['STORAGE_TYPE'],
                    'bucket_name':storageinfo['BUCKET_NAME'],
                    "conn_obj": CMinioManager(
                        storageinfo['ACCESS_KEY'],
                        storageinfo['SECRET_KEY'],
                        storageinfo['BUCKET_NAME'],
                        storageinfo['END_POINT']
                    )
                }
            elif "local" == storageinfo['STORAGE_TYPE']:
                conn_obj = {
                    "conn_name":conn_name,
                    "conn_type":storageinfo['STORAGE_TYPE'],
                    "conn_obj" :CLocalDisk(storageinfo['BUCKET_PATH'])
                }
            if (conn_obj != None):
                self.cloud_storage_pool.append(conn_obj)
        return conn_obj
