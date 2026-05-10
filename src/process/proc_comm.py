"""
{
    "FunDesc": "把数据从minio同步到本地",
    "ReqParam": {
        "dtype": "syncFilesFromMino2LocalDisk",
        "src_storage_conn_name": "ds_pg_minio",
        "src_path" :"AIDataManage/CskinWrinkle",
        "dst_storage_conn_name": "ds_pg_gpu_work_data",
        "dst_path": "cskin_wrinkle",
        "sync_mode": "IncSync"  #同步方式（注意：全量同步 FullSync 比较危险，慎重）
    }
}

{
    "FunDesc": "把数据从本地同步到minio",
    "ReqParam": {
        "dtype": "syncFilesFromLocalDisk2Minio",
        "src_storage_conn_name": "ds_pg_gpu_work_data",
        "src_path" :"cskin_wrinkle",
        "dst_storage_conn_name": "ds_pg_minio",
        "dst_path": "AIDataManage/CskinWrinkle",
        "sync_mode": "IncSync"  #同步方式（注意：全量同步 FullSync 比较危险，慎重）
    }
}
"""

# 基础process类
class CProcessComm:
    def __init__(self,node_cfg,storage_cloud):
        self.node_cfg = node_cfg
        self.storage_cloud = storage_cloud
        self.dconn_name = self.node_cfg['cloud_storage_dconn_cfg']

        
    def getNodeCfg(self):
        return self.node_cfg
    
    def getStorageCloudObj(self):
        return self.storage_cloud
    
    def syncFilesFromMino2LocalDisk(self,cmd_param):
        """
        @param  src_storage_conn_name  连接的存储名称
        @param  src_path  源路径（相对路径）
        @param  dst_storage_conn_name  连接的存储名称
        @param  dst_path  目标路径（相对路径）
        @param  sync_mode  同步模式，
                            IncSync:增量同步,同步增加、修改文件
                            FullSync:全量同步,同步增加、修改、删除文件
        """

        self.storage_cloud.syncFilesBetweenStorages(cmd_param['src_dconn_name'],
                                                        cmd_param['src_path'],
                                                        cmd_param['dst_dconn_name'],
                                                        cmd_param['dst_path'],
                                                        cmd_param['sync_mode']) 
    
    def syncFilesFromLocalDisk2Minio(self,cmd_param):
        """
        @param  src_storage_conn_name  连接的存储名称
        @param  src_path  源路径（相对路径）
        @param  dst_storage_conn_name  连接的存储名称
        @param  dst_path  目标路径（相对路径）
        @param  sync_mode  同步模式，
                            IncSync:增量同步,同步增加、修改文件
                            FullSync:全量同步,同步增加、修改、删除文件
        """
        self.storage_cloud.syncFilesBetweenStorages(cmd_param['src_dconn_name'],
                                                        cmd_param['src_path'],
                                                        cmd_param['dst_dconn_name'],
                                                        cmd_param['dst_path'],
                                                        cmd_param['sync_mode'])





    # 在两个存储之间同步文件
    def syncFilesBetweenStorages(self,cmd_param):
        """
        @param  src_storage_conn_name  连接的存储名称
        @param  src_path  源路径（相对路径）
        @param  dst_storage_conn_name  连接的存储名称
        @param  dst_path  目标路径（相对路径）
        @param  sync_mode  同步模式，
                            IncSync:增量同步,同步增加、修改文件
                            FullSync:全量同步,同步增加、修改、删除文件
        """
        try:
            self.storage_cloud.syncFilesBetweenStorages(cmd_param['src_storage_conn_name'],
                                                            cmd_param['src_path'],
                                                            cmd_param['dst_storage_conn_name'],
                                                            cmd_param['dst_path'],
                                                            cmd_param['sync_mode'])
            
        except Exception as e:
            self.storage_cloud.syncFilesBetweenStorages(cmd_param['src_storage_conn_name'],
                                                            cmd_param['src_path'],
                                                            cmd_param['dst_storage_conn_name'],
                                                            cmd_param['dst_path'],
                                                            cmd_param['sync_mode'])