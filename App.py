import sys
import os
dir_name = os.path.basename(os.path.dirname(__file__))
sys.path.append("./src/tools/{}/".format(dir_name))
from src.Process import CProcessor


class CApp:
    def __init__(self, node_cfg, progress_callback) :
        self.node_cfg = node_cfg
        #运行日志变量
        self.progress_callback = progress_callback

        #process对象
        self.processor  = CProcessor(self.node_cfg, self.progress_callback)

    def ProcessTask(self,param):
        self.processor.ProcessTask(param)
    
    def ProcessAPI(self,apitype,apimodule,apiclass, apimethod, param):
        """
        执行任务
        @param apitype: api类型(api / html 两种对应两种类型的接口)
        @param apimodule: 模块名称
        @param apiclass: 类名称
        @param apimethod: 方法名称
        @param param: 方法参数
        """
        res = {}
        try:
            res = self.processor.ProcessAPI(apitype,apimodule,apiclass, apimethod, param)
        except Exception as e:
            res = {
                'code': -1,
                'msg': 'failed',
                'data': {},
            }
            
        return res
    
    def Cleanup(self):
        """
        @param: None 你保存的第三方处理过程
        """
        pass

    def GetTaskReport(self):
        pass

    def GetTaskFinalReport(self):
        pass

    def onClose(self):
        print(f'{self.node_cfg["tool_package_snumber"]}工具退出')
        pass


