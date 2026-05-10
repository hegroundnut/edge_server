"""
根据toolconfig.yml的配置, 推送配置平台
step2 基于工具包+工具id, 推送json串
"""
import os
import requests
import yaml
import argparse
from minio import Minio
from minio.deleteobjects import DeleteObject
from tqdm import tqdm


def parse_args():
    parser = argparse.ArgumentParser(description="A script to interact with MinIO and process data.")
    # 默认配置你需要的命令行参数
    parser.add_argument('--plt-url', type=str, default="http://47.99.114.182:6061/aiserver/serverToolVersion/open/update", help="平台url")
    parser.add_argument('--storage-url', type=str, default="work.datashell.cn:1504",
                        help="存储url")
    parser.add_argument('--tools-yml', type=str, default="./toolconfig.yml", help="工具配置文件路径")

    # 必选配置
    parser.add_argument('--sync', type=str, required=True, help="同步模式, 文件或者参数file || params")
    parser.add_argument('--tool-name', type=str, required=True, help="工具名称, demo")
    parser.add_argument('--tool-version', type=str, required=True, help="工具版本, x.x.0")

    # 解析并返回参数
    return parser.parse_args()

class CSync2Plat:
    def __init__(self, args):
        self.args = args
        self.url = self.args.plt_url
        tool_yml = self.args.tools_yml
        with open(tool_yml, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.tool_package_snumber = self.config['tool_package_snumber'] # 工具包名称

    def sync(self):
        if self.args.sync == 'files':
            self.sync_file()
        if self.args.sync == 'params':
            self.sync_params()

    def sync_params(self):
        tools_sync_cfgs = self.config['tools_sync_cfgs']
        url = self.url.strip('/')
        
        tool_name = self.args.tool_name
        tool_version = self.args.tool_version
        try:
            cfg = tools_sync_cfgs[tool_name][tool_version]
        except KeyError:
            print("工具: {} - 版本: {},  本地配置不存在".format(tool_name, tool_version))
            return
        tool_uniq_id = cfg['tool_uniq_id']
        
        data = {
            "versionId": tool_uniq_id,                       # 工具的id
            "toolName": self.tool_package_snumber,           # "ds_tpsvr_0003_GPU"
            "toolUseFormat": cfg['tool_cfg']                 # 平台json串
        }

        for _ in tqdm(range(1)):
            try:
                response = requests.post(url, json=data)
                if response.status_code == 200:
                    print("工具: {} - 版本: {},  同步成功".format(tool_name, tool_version))
                else:
                    print("工具: {} - 版本: {},  同步失败, 错误信息: {}".format(tool_name, tool_version, response.text))

            except Exception as e:
                print("工具: {} - 版本: {},  同步失败, 错误信息: {}".format(tool_name, tool_version, e))

    def version_fmt(self):
        # 0.0.0转换成v0_0_0
        return 'v' + self.args.tool_version.replace('.', '_')

    def sync_file(self):
        # 创建 MinIO 客户端
        storage_url = self.args.storage_url
        client = Minio(
            storage_url,  # MinIO 地址
            secure=True  # 是否使用 HTTPS
        )

        remote_dir = 'ds-ai-svr/' + self.tool_package_snumber.strip('/') + '/' + self.args.tool_name.strip('/') + '/' + self.version_fmt() + '/'
        # 删除远程文件夹下所有的文件
        self.del_remote_files(client, remote_dir)
        
        # 上传新文件夹
        loc = 'src/features/'+self.args.tool_name.strip('/') + '/' + self.version_fmt().strip('/')
        # 去除__pycache__目录, 并用os.path.join(loc把这些连接起来
        sync_lists = [os.path.join(loc, f) for f in os.listdir(loc) if f not in ['__pycache__']]
        for file in tqdm(sync_lists):
            # 远程目录是"ds-ai-svr"+工具名称+verion(v0_0_0)以及下面的各层级
            remote_file = remote_dir + os.path.basename(file)
            # 获取文件大小
            file_size = os.path.getsize(file)

            # 打开文件并上传
            with open(file, "rb") as file_data:
                client.put_object(
                    "ds-base-ware",  # 桶名称
                    remote_file,            # 文件名
                    file_data, 
                    length=file_size  # 显式提供文件大小
                )

    def del_remote_files(self, client, remote_dir):
        try:
            # 1. 获取对象列表
            objects = client.list_objects("ds-base-ware", prefix=remote_dir, recursive=True)
            
            # 2. 将对象名称转换为 DeleteObject 实例 (这是关键)
            # 注意：确保 obj.object_name 是完整的路径
            delete_list = [DeleteObject(obj.object_name) for obj in objects]
            
            if delete_list:
                # 3. 批量删除
                errors = client.remove_objects("ds-base-ware", delete_list)
                
                # remove_objects 是延迟执行的生成器，需要遍历它才能触发删除并检查错误
                for error in errors:
                    print("工具: {} - 版本: {}, 同步信息: {}".format(self.args.tool_name, self.args.tool_version, error))
                
                print("工具: {} - 版本: {},  文件同步成功".format(self.args.tool_name, self.args.tool_version))
            else:
                print("工具: {} - 版本: {},  文件同步成功".format(self.args.tool_name, self.args.tool_version))
                
        except Exception as e:
            print("工具: {} - 版本: {},  文件同步失败, 错误信息: {}".format(self.args.tool_name, self.args.tool_version, e))

def main():
    args = parse_args()
    c2p = CSync2Plat(args)
    c2p.sync()


if __name__ == '__main__':
    # 通过添加args参数来实现
    """
    使用示例: 
        python tool_sync2plat.py --sync <files || params> --tool-name <你的工具名称> --tool-version <你的工具版本>
    完整命令: 
        # 以工具名称为demo, 版本为0.0.0, 同步参数和文件
        python tool_sync2plat.py --sync params --tool-name demo --tool-version 0.0.0         # 同步参数, 会完整覆盖平台参数
        python tool_sync2plat.py --sync files --tool-name demo --tool-version 0.0.0          # 同步文件, 会完整覆盖上一次的文件
    """
    main()