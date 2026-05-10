import oss2
import yaml
import os
import sys
import shutil
from pathlib import Path

from util.log import setup_custom_logger

logger = setup_custom_logger('LOCALDISK')

# 把远程的Linux/MacOS 磁盘当作一个存储（scp命令）
class CRemoteLinux(object):

    def __init__(self, disk_root_path):
        self.disk_root_path = disk_root_path