import os
import requests
from os import mkdir
from util.log import setup_custom_logger

logger = setup_custom_logger("UrlRequest")

class UrlRequest(object):

    def __init__(self, node_cfg):
        self.node_cfg = node_cfg

    def url_post(self,urlsvr,urlname,param):
        res = {}
        try:
            url = "{}/{}/".format(urlsvr.strip("/"),urlname.strip("/"))
            send_data = param
            try:
                res = requests.post(url,data=send_data).json()
                if 0 == res["status"]:
                    return res
                else:
                    logger.error("get init config failed")
                    return res
            except Exception as e:
                logger.error("get init config error: {}".format(str(e)))
                return res
        except Exception as e:
            logger.error("get init config error: {}".format(str(e)))
            return res

    # 获取项目配置信息
    def get_project_config(self):
         # 如果没有该连接信息，则向服务端读取基本的cskin配置信息
        try:
            url = "{}/get-project-config/".format(self.node_cfg['plt_url'])
            send_data = {
                "client_key": "111111"
            }
            try:
                res = requests.post(url,data=send_data).json()
                if 0 == res["status"] :
                    prjcfg = res["data"]
                    return prjcfg
                else:
                    logger.error("get init config failed")
                    return {}
            except Exception as e:
                logger.error("get init config error: {}".format(str(e)))
                return {}
        except Exception as e:
            logger.error("get init config error: {}".format(str(e)))
            return {}

    """
    查询cloud storage的连接信息
    """
    # TODO: 还没有实现
    def get_storage_info_byname(self,conn_name):
        try:
            url = "{}/get-storage-config/".format(self.node_cfg['plt_url'])
            send_data = {
                "dconn_name": conn_name,
                "client_key": "111111"
            }
            conn_info = requests.post(url,data=send_data).json()
            if 0 == conn_info["status"]:
                data = conn_info["data"]
                return data

        except Exception as e:
            return {}