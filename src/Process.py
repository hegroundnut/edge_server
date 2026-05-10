import os
import shutil
import time
import json
import traceback
from collections import defaultdict
from src.conn.Storages import StoragesMng
from src.process.proc_comm import CProcessComm
from src.Util import *

dir_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
ABSPATH = 'src.tools.{}.src.features.'.format(dir_name)

class CProcessor(object):
    def __init__(self, node_cfg, progress_callback):
        super(CProcessor, self).__init__()
        self.node_cfg = node_cfg
        self.proc_modules_obj = {}   # 图像模块
        self.train_modules_obj = defaultdict(dict)  # 训练模块
        self.progress_callback = progress_callback # 回调模块
        self.func_idx = 0       # 功能序号
        self.subtask_idx = -2   # 子功能
        # 进度: -2为手动触发异常, 表示这是一个功能; -1为程序异常, 0-100为正常

        # 工具临时目录初始化
        if os.path.exists(self.node_cfg['tmp_data']):
            shutil.rmtree(self.node_cfg['tmp_data'])
        os.makedirs(self.node_cfg['tmp_data'], exist_ok=True)
        self.storage_cloud = StoragesMng(self.node_cfg,self.proc_modules_obj,self.progress_callback)
        self.process_comm = CProcessComm(self.node_cfg,self.storage_cloud)
        self.priv_load_train_version("train_cfg") # TODO: train_cfg应该是实打实的配置文件

    
    def ProcessTask(self, params):
        """
        @param: dict 包含了你提交的函数入参信息，由用户的文件自行解析
        """
        for func_idx, param in enumerate(params): # 功能层级
            self.func_idx = func_idx
            funcname = param['dtype']
            version = param['version']

            func = self.train_modules_obj[funcname][version]
            is_a_single_func = False # 标识这是一个单独的功能,还是有功能子项的功能

            # 执行功能任务
            try:
                subTaskParams = param['subfuncs'] # 功能子任务层级, 类似cskin的业务没有子任务的概念的
            except Exception as e:
                is_a_single_func = True
                self.progress_callback(-2, "功能名称: {}, 无功能子项, 直接执行....".format(funcname), func_callback=[self.func_idx, self.subtask_idx])
                raise e


            if is_a_single_func == True: # 单独功能直接运行, 功能子项则遍历运行
                try:
                    if hasattr(func, funcname):
                        getattr(func, funcname)(param)
                except Exception as e:
                    traceback_err_msg = traceback.print_exc() # 把异常信息返回去
                    print("功能名称: {}, 异常原因: {}".format(funcname, traceback_err_msg))
                    self.progress_callback(-1, traceback_err_msg, func_callback=[self.func_idx, self.subtask_idx])
                    raise e

                continue
            
            else:
                # 执行功能下面的子任务, 如果没有子任务则不执行
                try:
                    for subtask_idx, subTask in enumerate(subTaskParams):
                        self.subtask_idx = subtask_idx
                        subtask_name = subTask['func_name']
                        self.progress_callback(-2, "功能名称: {}, 功能子项名称: {}".format(funcname, subtask_name), func_callback=[self.func_idx, self.subtask_idx])
                        subtask_param = subTask['params']
                        if hasattr(func, subtask_name):
                            getattr(func, subtask_name)(subtask_param)
                except Exception as e:
                    traceback_err_msg = traceback.print_exc() # 把异常信息返回去
                    print("功能名称: {}, 功能子项名称({}/{}): {},  异常原因: {}".format(funcname, self.func_idx, self.subtask_idx, subtask_name, traceback_err_msg))
                    self.progress_callback(-1, traceback_err_msg, func_callback=[self.func_idx, self.subtask_idx])
                    raise e

        
    def onClose(self):
        pass


    # 加载算法版本模块文件
    def priv_load_train_version(self, train_cfg):
        # TODO: train_cfg作为入参, 得参考开放平台是否有网关: 建议有, 【这样可以比较明确到底有哪些模型可以被训练】
        """
        加载的算法模块名称
        {
        '模型对象名称': '模型模块名称',
        }
        """
        # 加载对应的数据处理模块, 比如同步
        proc_modules_files = {}
        train_modules_files = defaultdict(dict)
        proc_modules_files['imgbase'] = loadPyFile('imgbase', 'CImgBase', '{}{}'.format(ABSPATH, 'common')) # 公共函数-base
        for proc_name in proc_modules_files:
            self.proc_modules_obj[proc_name] = proc_modules_files[proc_name](self.progress_callback)
        self.train_modules_obj['DsStorages']['0.0.0'] = self.process_comm

        # 何桐  数据分桶处理 - 修改为与其他模块一致的加载方式
        # train_modules_files['organizeUavData']['0.0.0'] = loadPyFile('dataOrganize', 'CDataOrganize', '{}{}'.format(ABSPATH, 'dataOrganize'))

        # 加载对应的训练模块, 比如各类模型的训练
        # train_modules_files['trainVideoTracking']['0.0.0'] = loadPyFile('trainVideoTracking', 'CTrainVideoTracking', '{}{}'.format(ABSPATH, 'videoTracking.0_0_0')) # 目标追踪
        

        train_modules_files = self._load_train_version()


        # 加载所有训练模块的对象
        for train_name in train_modules_files:
            print("train_name: ", train_name)
            for version in train_modules_files[train_name]:
                try: # try的原因是某些功能未实现, 即对象部分如果是None就不支持实例化
                    self.train_modules_obj[train_name][version] = train_modules_files[train_name][version](self.node_cfg, self.process_comm, self.proc_modules_obj, self.progress_callback)
                except Exception as e:
                    logger.error("Process.priv_load_train_version: {}".format(e))
                    continue

    def _load_train_version(self):
        train_modules_files = defaultdict(dict)
        # ABSPATH 已经处理好，例如 "apps.train_modules."
        rel_path = ABSPATH.rstrip('.').replace('.', os.sep)
        base_path = rel_path 

        if not os.path.exists(base_path):
            logger.error(f"Path not found: {base_path}")
            return train_modules_files
        loading_tools = self.node_cfg['loading_tools']
        if 1 != 1:
            for root, dirs, files in os.walk(base_path):
                if 'loading.json' in files:
                    json_path = os.path.join(root, 'loading.json')
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            config_lists = json.load(f)
                        
                        if not isinstance(config_lists, list):
                            continue

                        for cf_data in config_lists:
                            # 1. 提取变量
                            dtype = cf_data.get('dtype')
                            version_raw = cf_data.get('version')
                            file_name = cf_data.get('file_name')
                            class_name = cf_data.get('class_name')
                            dir_name = cf_data.get('dir_name')

                            # 2. 核心数据校验
                            if not all([dtype, version_raw, file_name, class_name]):
                                continue

                            # 3. 核心加载逻辑（放入循环内！）
                            try:
                                version_fmt = version_raw.replace('.', '_')
                                # 确保 ABSPATH 结尾有点，或者在这里补上
                                full_mod_path = f"{ABSPATH}{dir_name}.v{version_fmt}"
                                
                                module_obj = loadPyFile(file_name, class_name, full_mod_path)
                                if module_obj:
                                    train_modules_files[dtype][version_raw] = module_obj
                            except Exception as e:
                                logger.error(f"Failed to load module {dtype} v{version_raw} in {json_path}: {e}")
                                
                    except Exception as e:
                        logger.error(f"Failed to read or parse {json_path}: {e}")
                        continue
        else:
            for cf_data in loading_tools:
                try:
                    # 1. 提取变量
                    dtype = cf_data.get('dtype')   # 👉建议后面改成 task_type
                    version_raw = cf_data.get('version')
                    file_name = cf_data.get('file_name')
                    class_name = cf_data.get('class_name')
                    dir_name = cf_data.get('dir_name')

                    # 2. 校验
                    if not all([dtype, version_raw, file_name, class_name]):
                        continue

                    # 3. 加载
                    version_fmt = version_raw.replace('.', '_')
                    full_mod_path = f"{ABSPATH}{dir_name}.v{version_fmt}"
                    module_obj = loadPyFile(file_name, class_name, full_mod_path)

                    if module_obj:
                        train_modules_files[dtype][version_raw] = module_obj

                except Exception as e:
                    logger.error(f"Failed to load module {cf_data}: {e}")
        # time.sleep(40)

        return train_modules_files