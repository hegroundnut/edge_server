"""
公共函数-基础图像处理函数
"""

import os
# import pyheif
import shutil
import cv2
import numpy as np
import io
import json
import time
from tqdm import tqdm
# from PIL import Image
from pathlib import Path



class CImgBase():
    def __init__(self, progress_callback):
        self.progress_callback = progress_callback

    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<脸部绘图标准函数  START<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    # 为了统一轮廓绘制，这里将轮廓绘制函数封装起来
    def drawImgWithFaceContours(self, img, img_type, face_contours = None,isfill = False,face_mask = None):
        """
        在图像上绘制轮廓
        @param img 原始图像
        @param img_typ 图像颜色 white/red/brown/green
        @param contours 轮廓列表
        @param isfill 是否填充轮廓
        @param face_mask 轮廓掩码
        @return 绘制了轮廓的图像
        """
        contour_color = (0,0,0)
        if (img_type == 'white'):
            contour_color = (0,0,255)
            fill_color = (255,255,0)
        elif (img_type == 'red'):
            contour_color = (255,0,0)
            fill_color = (0,0,255)
        elif (img_type == 'brown'):
            contour_color = (0,255,0)
            fill_color = (255,0,0)
        if face_contours != None:
            img = self.drawImgWithContours(img,face_contours,contour_color,3,isfill,fill_color)
        elif face_mask != None:
            contours, _ = cv2.findContours(face_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            img = self.drawImgWithContours(img,contours,contour_color,3)   
        return img
    
    # 在图像上叠加二值图mask
    def drawImgWithMask(self, img, mask, color, constrain_mask=None, alpha=1):
        """
        在图像上叠加二值图 mask，并支持设置透明度。

        :param img: 原图 (numpy array, BGR 彩色图)
        :param mask: 二值图 (numpy array，单通道灰度图)
        :param color: 要叠加的颜色 (B, G, R)
        :param constrain_mask: 限定的区域（二值图），只在该区域叠加
        :param alpha: 透明度，0 表示完全透明，1 表示完全不透明
        :return: 叠加后的图像
        """
        img = img.copy()
        if constrain_mask is not None:
            mask = cv2.bitwise_and(mask, constrain_mask)

        # 检查 mask 是单通道
        if len(mask.shape) != 2:
            raise ValueError("mask 必须是单通道图像")

        # 生成与原图相同大小的纯色图（要叠加的颜色）
        color_img = np.full_like(img, color, dtype=np.uint8)

        # 创建 mask 区域三通道版
        mask_bool = mask > 0
        mask_3c = np.stack([mask_bool] * 3, axis=-1)  # (H, W, 3)

        # 执行加权融合，仅在 mask 区域
        img[mask_3c] = (img[mask_3c] * (1 - alpha) + color_img[mask_3c] * alpha).astype(np.uint8)

        return img

    # 为了统一色斑绘制，这里将色斑绘制函数封装起来
    def createMaskByContoursForFace(self,contours,img_type ,img_shape):
        """
        在图像上绘制轮廓
        @param img_typ 图像颜色 white/red/brown/green
        @param contours 轮廓列表
        @param img_shape: 图像形状（高、宽）
        @return: 3通道透明掩码图像
        """
        contour_color = (0,0,0)
        fill_color = (0,0,0)
        if (img_type == 'white'):
            contour_color = (0,255,0)
            fill_color = (0,0,255)
        elif (img_type == 'red'):
            contour_color = (0,255,0)
            fill_color = (255,0,0)
        elif (img_type == 'brown'):
            contour_color = (0,255,0)
            fill_color = (0,0,255)
        
        return self.createMaskByContours(contours,img_shape,True,1,contour_color,True,fill_color)

    # 更新report json的功能
    def write_json(self,json_path, update_dict):
        """
        打开 json 文件，若存在则替换键值；不存在则创建并写入 update_dict
        @params: json_path  json文件存储路径
        @params: update_dict 要更新或者追加的键值对
        """
        data = {}
        # 1. 如果文件存在，先读取旧数据
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    print("JSON 文件为空或格式错误，重新写入")

        # 2. 替换或追加新值
        data.update(update_dict)

        # 3. 写回文件
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    #>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>脸部绘图标准函数  END>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>


    def saveMaskToRGBAPng(self, mask):
        """
        mask对象, 透明部分黑色（0）其他部分白色（255）
        :param mask: 二值图对象
        :return: mask对象
        """
        # 二值图转成rgba, 把白色的地方变成红色
        _, mask = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)
        rgba = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGBA)
        rgba[:, :, 0] = 0
        rgba[:, :, 1] = 0
        rgba[:, :, 2] = 255
        rgba[:, :, 3] = mask
        return rgba

    # 读取png图成为mask对象，透明部分黑色（0）其他部分白色（255）
    def readMaskFromPng(self, pngfilename):
        """
        读取png图成为mask对象，透明部分黑色（0）其他部分白色（255）
        :param pngfilename: png文件路径或者mask对象
        :return: mask对象
        """
        # 读取包含Alpha通道的图像
        try:
            img = cv2.imread(pngfilename, cv2.IMREAD_UNCHANGED)
        except Exception as e:
            img = pngfilename
        
        # 检查是否包含Alpha通道(通道数为4)
        if img is not None and img.shape[2] == 4:
            # 分离Alpha通道
            _, _, _, alpha = cv2.split(img)
            # 创建二值掩码: 透明区域(alpha=0)设为0，不透明区域设为255
            mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
        else:
            # 若无Alpha通道，使用灰度读取并强制二值化
            mask = cv2.imread(pngfilename, cv2.IMREAD_GRAYSCALE)
            _, mask = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)
        return mask


    # 在图像上绘制矩形轮廓
    def drawImgWithRect(self,img,rect,color=(0,0,255),thickness=2):
        """
        在图像img上绘制矩形rect
        
        :param img: 图像对象 (numpy array)
        :param rect: 矩形坐标，格式为 (x1, y1, x2, y2)，其中 (x1,y1) 是左上角坐标，(x2,y2) 是右下角坐标
        :return: 绘制了矩形的图像
        """
        # 确保 img 是一个 numpy 数组
        img = np.array(img)
        
        # 创建一个与 img 大小相同的副本，用于绘制矩形
        result_img = img.copy()
        
        # 检查rect是否为空
        if rect is None:
            return result_img
        
        try:
            # 尝试直接绘制矩形
            # 假设rect格式为(x1, y1, x2, y2)
            x1, y1, x2, y2 = rect
            # 确保坐标是整数
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            # 绘制矩形（默认为红色，线宽为2）
            cv2.rectangle(result_img, (x1, y1), (x2, y2), color, thickness)
        except Exception as e:
            # 如果出现错误，记录错误并返回原始图像
            print(f"绘制矩形时出错: {str(e)}")
            
        return result_img

    # 提取二值图像的轮廓
    def findMaskContours(self, mask):
        """
        输入二值图像, 返回此图像轮廓
        @params: json_path  json文件存储路径
        @params: update_dict 要更新或者追加的键值对
        """
        _, mask = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        mask_contours = []
        contours_area = 0

        for contour in contours:
            mask_contours.append(contour)

        return mask_contours

    # 计算输入的img图像的所有轮廓的平均值(一般只适合计算小轮廓，比如ita角，否则计算速度太慢)
    # TODO: 未测试
    def getImgAvgValInContours(self,img,contours):
        """
        计算输入的img图像的所有轮廓的平均值(一般只适合计算小轮廓，比如ita角，否则计算速度太慢)
        @param: contours 轮廓
        @param: img 输入图像
        @return: 所有轮廓的平均值（根据img的通道数返回对应的元组）,比如3通道图像返回 (a,b,c)
        """
        ret_channel_avg = []
        # 读取输入img的通道数
        channel_num = len(img.shape)
        for i in channel_num:
            channel = img[:,:,i]
            # 计算当前通道的平均值
            channel_avg = np.mean(channel[contours])
            ret_channel_avg.append(channel_avg)
        
        return ret_channel_avg

    # 在图像上合并一个mask图
    def combineImgBy1ChannelMask(self,img,mask,color):
        """
        在图像对象 img 上合并一个 mask 图像（单通道图）。

        :param img: 图像对象 (numpy array)
        :param mask: mask 图像对象 (numpy array，单通道图)
        :param color: mask 叠加用的颜色 (B, G, R)
        :return: 合并后的图像
        """
        # 确保 img 和 mask 是 numpy 数组
        img = np.array(img)
        mask = np.array(mask)
        
        # 确保 mask 是一个单通道的图
        if len(mask.shape) != 2:
            raise ValueError("mask 必须是一个单通道的图")
        
        # 创建一个与 img 大小相同的彩色 mask 图像
        mask_color = np.full_like(img, color)
        
        # 归一化 mask 到 0-1 范围
        if np.max(mask) > 0:
            mask_normalized = mask / np.max(mask)
        else:
            mask_normalized = mask.copy()
        
        # 扩展 mask 维度以匹配 img 的通道数
        mask_normalized_3d = np.repeat(mask_normalized[:, :, np.newaxis], 3, axis=2)
        
        # 将 mask_normalized_3d 转换为与 img 相同的数据类型
        mask_normalized_3d = mask_normalized_3d.astype(img.dtype)
        
        # 使用 NumPy 的向量化操作实现图像混合
        combined_img = img * (1 - mask_normalized_3d) + mask_color * mask_normalized_3d
        
        # 确保结果在有效范围内并转换回整数类型
        combined_img = np.clip(combined_img, 0, 255).astype(np.uint8)
        
        return combined_img


    def combineImgBy3ChannelMask(self, img, mask):
        """
        把mask（3通道图像）合并到img上
        @param img 原始图像
        @param mask 3通道掩码图像
        @return 合并后的图像
        """
        # 1. 确保图像和掩码都是numpy数组
        img = np.array(img)
        mask = np.array(mask)

        # 2. 检查图像和掩码是否有相同的高度和宽度
        if img.shape[:2] != mask.shape[:2]:
            raise ValueError("图像和掩码必须有相同的高度和宽度")
        
        # 3. 确保mask是3通道
        if len(mask.shape) < 3 or mask.shape[2] != 3:
            raise ValueError("掩码必须是3通道图像")
        
        # 4. 确保img至少有3通道
        img_3ch = img[:, :, :3].copy() if len(img.shape) >= 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        
        # 5. 创建一个输出图像的副本
        result = img_3ch.copy()
        
        # 6. 合并图像和掩码
        # 检查mask中哪些像素不是黑色（即有内容的区域）
        mask_non_black = (mask[:, :, 0] > 0) | (mask[:, :, 1] > 0) | (mask[:, :, 2] > 0)
        
        # 在mask非黑色区域，将mask的像素值赋给结果图像
        result[mask_non_black] = mask[mask_non_black]
        
        return result

    def createMaskByContours(self,contours,img_shape,isDrawLines,lineWidth,lineColor,isFill,fillColor):
        """
        根据轮廓创建掩码mask
        :param contours: 轮廓列表
        :param img_shape: 图像形状（高、宽）
        :param isDrawLines: 是否绘制轮廓线 True / False
        :param lineWidth: 轮廓线宽度
        :param lineColor: 轮廓线颜色 (B, G, R) 3通道颜色
        :param isFill: 是否填充轮廓区域 True / False
        :param fillColor: 填充颜色 (B, G, R) 3通道颜色
        :return: 3通道透明掩码图像
        """
        # 只使用图像的高度和宽度，忽略通道数
        height, width = img_shape[:2]
        # 创建3通道的透明空白图
        mask = np.zeros((height, width, 3), dtype=np.uint8)

        # 确保contours是有效的格式（列表中的numpy数组）
        if contours is None or len(contours) == 0:
            return mask
            
        if isFill:
            cv2.drawContours(mask, contours, -1, fillColor, -1)
        if isDrawLines:
            cv2.drawContours(mask, contours, -1, lineColor, lineWidth)
        return mask

    def intersectionArea(self,contour1,contour2):
        # 方法1：如果OpenCV版本支持cv2.intersectionArea函数（较新版本）
        # 直接使用内置函数计算轮廓交集面积
        # intersection_area = cv2.intersectionArea(brown_cnt, red_cnt)
        
        # 方法2：兼容性更好的实现，适用于所有OpenCV版本
        # 创建包含两个轮廓的最小外接矩形
        x1, y1, w1, h1 = cv2.boundingRect(contour1)
        x2, y2, w2, h2 = cv2.boundingRect(contour2)
        # 判断两个外接矩形，如果没有重叠，则返回0
        if x1 + w1 < x2 or x2 + w2 < x1 or y1 + h1 < y2 or y2 + h2 < y1:
            return 0
        
        # 计算包含两个轮廓的最小矩形
        x_min = min(x1, x2)
        y_min = min(y1, y2)
        x_max = max(x1 + w1, x2 + w2)
        y_max = max(y1 + h1, y2 + h2)
        
        # 创建两个掩码图像
        width = x_max - x_min + 10  # 增加一些边距
        height = y_max - y_min + 10
        mask1 = np.zeros((height, width), dtype=np.uint8)
        mask2 = np.zeros((height, width), dtype=np.uint8)
        
        # 调整轮廓坐标以适应临时图像
        adj_contour1 = contour1 - np.array([x_min - 5, y_min - 5])
        adj_contour2 = contour2 - np.array([x_min - 5, y_min - 5])
        
        # 在掩码上绘制并填充轮廓
        cv2.drawContours(mask1, [adj_contour1], -1, 255, -1)
        cv2.drawContours(mask2, [adj_contour2], -1, 255, -1)
        
        # 计算两个掩码的交集
        intersection_mask = cv2.bitwise_and(mask1, mask2)
        
        # 计算交集区域的面积（非零像素的数量）
        intersection_area = cv2.countNonZero(intersection_mask)
        return intersection_area

    def intersectionContour(self, contour1, contour2):
        """
        计算两个轮廓的交集
        :param contour1: 第一个轮廓
        :param contour2: 第二个轮廓
        :return: 交集轮廓(多个轮廓)
        """
        # 确定轮廓的边界框以创建适当大小的临时图像
        x1, y1, w1, h1 = cv2.boundingRect(contour1)
        x2, y2, w2, h2 = cv2.boundingRect(contour2)

        # 根据外边框直接判断如果没有交集，直接返回[]
        if x1 + w1 < x2 or x2 + w2 < x1 or y1 + h1 < y2 or y2 + h2 < y1:
            return []
        
        # 计算包含两个轮廓的最小矩形
        x_min = min(x1, x2)
        y_min = min(y1, y2)
        x_max = max(x1 + w1, x2 + w2)
        y_max = max(y1 + h1, y2 + h2)
        
        # 创建临时图像，大小足以包含两个轮廓
        width = x_max - x_min + 10  # 增加一些边距
        height = y_max - y_min + 10
        
        # 创建两个掩码图像
        mask1 = np.zeros((height, width), dtype=np.uint8)
        mask2 = np.zeros((height, width), dtype=np.uint8)
        
        # 调整轮廓坐标以适应临时图像
        adj_contour1 = contour1 - np.array([x_min - 5, y_min - 5])
        adj_contour2 = contour2 - np.array([x_min - 5, y_min - 5])
        
        # 在掩码上绘制并填充轮廓
        cv2.drawContours(mask1, [adj_contour1], -1, 255, -1)
        cv2.drawContours(mask2, [adj_contour2], -1, 255, -1)
        
        # 计算两个掩码的交集
        intersection_mask = cv2.bitwise_and(mask1, mask2)
        
        # 从交集中提取轮廓
        intersection_contours, _ = cv2.findContours(intersection_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not intersection_contours:
            # 如果没有交集，返回空列表
            return []
        
        ret_contours = []
        # 将提取的轮廓坐标调整回原始坐标系
        for contour in intersection_contours:
            contour = contour + np.array([x_min - 5, y_min - 5])
            ret_contours.append(contour)
        
        return ret_contours

        # 在图像上绘制轮廓(填充)
    def drawImgWithContours(self, img, contours, color, thickness=10, isfill=False, fillColor=(0,255,0)):
        """
        在图像上绘制多个轮廓。

        :param img: 图像对象 (numpy array)
        :param contours: 轮廓组，包含多个轮廓，每个轮廓是一个x、y坐标数组。
                        格式: [[[x,y],[x,y],[x,y],[x,y]],[[x,y],[x,y],[x,y],[x,y]]]
        :param color: 绘制轮廓的颜色 (B, G, R)
        :param thickness: 轮廓的线宽
        :return: 绘制了轮廓的图像
        """
        # 确保 img 是一个 numpy 数组
        img = np.array(img)
        
        # 创建一个与 img 大小相同的副本，用于绘制轮廓
        result_img = img.copy()
        
        # 检查contours是否为空
        if contours is None or len(contours) == 0:
            return result_img
        
        try:
            # 尝试直接绘制轮廓
            if isfill:
                cv2.drawContours(result_img, contours, -1, fillColor, -1)
            else:
                cv2.drawContours(result_img, contours, -1, color, thickness)
        except cv2.error:
            # 如果出现错误，尝试转换轮廓格式
            try:
                # 转换轮廓格式为OpenCV所需的(n,1,2)格式
                converted_contours = []
                for contour in contours:
                    # 确保轮廓是numpy数组
                    cnt = np.array(contour, dtype=np.int32)
                    # 检查并调整形状
                    if len(cnt.shape) == 2:
                        # 形状为(n,2)，需要转换为(n,1,2)
                        cnt = cnt.reshape(-1, 1, 2)
                    converted_contours.append(cnt)
                
                # 再次尝试绘制转换后的轮廓
                if isfill:
                    cv2.drawContours(result_img, converted_contours, -1, fillColor, -1)
                else:
                    cv2.drawContours(result_img, converted_contours, -1, color, thickness)
            except Exception as e:
                # 如果仍然失败，记录错误并返回原始图像
                print(f"绘制轮廓时出错: {str(e)}")
                
        return result_img

    # 把图像（4通道）转成mask（二值图）
    def convertImg2Mask(self,img,threshold_val=128):
        """
        读取png图成为mask对象，透明部分黑色（0）其他部分白色（255）
        :param img: 
        :param threshold_val 阈值，< threshold_val 黑色， > threshold_val 白色
        :return: mask对象
        """
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 检查是否包含Alpha通道(通道数为4)
        if img is not None and img.shape[2] == 4:
            # 分离Alpha通道
            _, _, _, alpha = cv2.split(img)
            # 创建二值掩码: 同时满足alpha>0且灰度值>阈值的像素设为255，否则设为0
            mask = np.zeros_like(alpha, dtype=np.uint8)
            mask[(alpha > 0) & (gray_img > threshold_val)] = 255
        else:
            # 若无Alpha通道，使用灰度读取并强制二值化
            mask = cv2.cvtColor(img,cv2.COLOR_RGB2GRAY)
            _, mask = cv2.threshold(mask, threshold_val, 255, cv2.THRESH_BINARY)
        return mask

    def get_contour_points(self, mask):
        """
        输入: mask (二值图, 0/255)
        输出: dict 格式的大轮廓边缘点
            key = 轮廓索引
            value = (N,2) 的坐标数组
        参数:
            min_area: 过滤小轮廓，保留大轮廓
        """
        # 找轮廓，保留所有边缘点
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        contour_dict = {}
        idx = 0
        for cnt in contours:
            cnt_2d = cnt.reshape(-1, 2)  # (N,1,2) -> (N,2)
           
            contour_dict[idx] = cnt_2d
            idx += 1
        return contour_dict
    
    #把一个mask图居中放到一个mask中
    def clip_middle_mask(self, face_mask, org_height, org_width):
        """
        @desc 把一个mask图居中放到一个mask中
        @params img_merge_rl: 目标大图，形状 (H, W, 3)
        @params face_mask: 小宽度的二值mask，形状 (H, mw)
        @return: (遮罩融合后的RGB图, 居中放置的全黑底mask图)
        """
        h, w = org_height, org_width
        mh, mw = face_mask.shape[:2]

        if mh != h:
            raise ValueError("face_mask 和 img_merge_rl 高度不一致，无法操作")

        # 创建和img_merge_rl同宽高的全黑mask
        clipping_face_mask = np.zeros((h, w), dtype=np.uint8)

        # 计算左右居中偏移
        x_offset = (w - mw) // 2

        # 水平方向居中放置face_mask
        clipping_face_mask[:, x_offset:x_offset + mw] = face_mask
        return clipping_face_mask

    # 用mask图对输入图像进行截取
    def cropImgWithMask(self,img,mask):
        """
        用mask图对输入图像进行截取
        :param img: 输入图像对象 (numpy array)
        :param mask: 二值图mask对象 (numpy array，单通道灰度图)
        :return: 截取后的图像
        """
        # 确保 img 和 mask 是 numpy 数组
        img = np.array(img)
        mask = np.array(mask)
        
        # 确保 mask 是一个单通道的二值图
        if len(mask.shape) != 2:
            raise ValueError("mask 必须是单通道的二值图")
        
        # 使用 mask 对 img 进行截取
        cropped_img = np.where(mask[:, :, np.newaxis] > 0, img, 0)
        
        return cropped_img

    # 把2d点画到图像上
    def drawLandmarkPointsToImg(self, img_bgr, points_2d):
        """
        把2d点画到图像上
        :param img_bgr: 输入图像对象 (numpy array)
        :param points_2d: 2d点数组 (numpy array，形状 (N,2))
        :return: 画了点的图像
        """
        # 3456宽*5184高的时候, 下面的参数是10和5, 我需要动态计算
        h, w, _ = img_bgr.shape
        radius = max(1, int(w // 345.6)) # radius<1的时候等于1
        
        thickness = 5
        for idx, pt in enumerate(points_2d):
            cv2.circle(img_bgr, (int(pt[0]), int(pt[1])), radius, (0, 0, 255), thickness)

        return img_bgr


    """
    heic2jpg转换 把source目录下的所有heic转换成jpg
    """
    def batchConverHeic2Jpg(self,source, destination):
        # 检查目标文件是否存在，如果存在则跳过转换
        """
        params: source          "<report_id>"目录
        params: destination     "<report_id>"目录
        """

        onlyfiles =[f for f in os.listdir(source) if os.path.isfile(os.path.join(source, f))]
        if not os.path.exists(destination):
            os.makedirs(destination)
        else:
            print("Output dir already exists")
        for file in onlyfiles:
            (name, ext) = os.path.basename(file).split('.')
            dest = os.path.join(destination, name) + '.jpg'
            # 检查目标文件是否已存在
            if os.path.exists(dest):
                print(f"File {dest} already exists, skipping conversion")
                continue
            
            if ext == 'heic' or ext == 'HEIC':
                sour= os.path.join(source, file)
                f=open(sour,"rb")
                bytesIo=f.read()
                fmt = whatimage.identify_image(bytesIo)
                print("fmt: ", fmt)
                if fmt in ['heic', 'avif']:
                    try:
                        i = pyheif.read_heif(bytesIo)
                    except pyheif.error.HeifError as e:
                        #raise TypeError from e
                        print("heic 2 jpg error")
                # Extract metadata etc
                    for metadata in i.metadata or []:
                        if metadata['type']=='Exif':
                            # do whatever
                            print("EXif")
                    # Convert to other file format like jpeg
                    s = io.BytesIO()
                    print("i.mode: ", i.mode)
                    pi = Image.frombytes(
                            mode=i.mode, size=i.size, data=i.data)
                    pi1 = pi.convert("RGB")
                    pi1.save(dest,quality=95)
                elif fmt == 'jpeg':
                    sour= os.path.join(source, file)
                    shutil.copyfile(sour,dest)
            elif ext == 'jpg' or ext == 'jpeg':
                sour= os.path.join(source, file)
                shutil.copyfile(sour,dest)

    def checkPreFileValid(self, folder_paths):
        """
        检查文件夹内的 .jpg/.jpeg/.png 是否破损，损坏即删除，并显示进度条。
        参数:
            folder_paths: str 或 Path 的列表
        返回:
            List[Path]: 被删除的损坏文件列表
        """

        deleted_files = []
        folders = [Path(p) for p in folder_paths]

        for folder in folders:
            if not folder.is_dir():
                print(f"[警告] 跳过无效路径：{folder}")
                continue

            print(f"\n====== 检查文件夹: {folder} ======")

            # 收集所有图片
            img_files = []
            for ext in ("*.jpg", "*.jpeg", "*.png"):
                img_files.extend(folder.glob(ext))

            if not img_files:
                print("[提示] 这个文件夹没有图片，跳过。")
                continue

            # tqdm 进度条
            pbar = tqdm(img_files, desc=f"Checking {folder.name}", unit="file")
            for file in pbar:
                try:
                    self.send_progress(pbar, deal_msg = 'checkPreFileValid file for Train model, curr check in {}'.format(file))
                    img = cv2.imread(str(file))
                    if img is None:
                        raise ValueError("OpenCV 无法解码")
                    _ = img.shape
                except Exception:
                    print(f"\n[损坏并删除] {file}")
                    file.unlink(missing_ok=True)
                    deleted_files.append(file)

        print("\n===== 全部文件夹处理完毕 =====")
        print(f"共删除 {len(deleted_files)} 个损坏文件。")

    def erode_mask_file(self, img_mask, kernel_size=4, toRGBA=False):
        """
        @description: 对二值掩膜图进行腐蚀操作, 可以把轮廓变小
        @params:
            root_dir: 要处理本地的根目录
            params: 处理函数的入参
        @return:
            
        """
        # 读取二值掩膜图（假设白色线条为255，背景为0）
        erodedRedMask = None
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))   # 定义腐蚀核的形状和大小（控制“收缩”的程度）
        eroded = cv2.erode(img_mask, kernel, iterations=1)                                  # 腐蚀操作(变细)
        if toRGBA:
            erodedRedMask = self.convertMaskToRGBA(eroded)                                        # 转回红色的png图
        return eroded, erodedRedMask


    # 批量腐蚀图像
    def erode_mask_dir(self, root_dir, params):
        """
        @description: 对二值掩膜图进行腐蚀操作, 可以把轮廓变小
        @params:
            root_dir: 要处理本地的根目录
            params: 处理函数的入参
        @return:
            
        """

        # 读取二值掩膜图（假设白色线条为255，背景为0）
        mask_dir = params['mask_dir']
        kernel_size = params.get('kernel_size', 4)

        root_dir = root_dir.rstrip('/')
        base_path = os.path.join(root_dir, mask_dir)

        # 收集所有 .png 文件路径
        mask_files = []
        for dirpath, _, filenames in os.walk(base_path):
            for f in filenames:
                if f.lower().endswith('.png'):
                    mask_files.append(os.path.join(dirpath, f))

        # tqdm 进度条
        pbar = tqdm(mask_files, desc="腐蚀掩膜中", ncols=80)
        for mask_abspath in pbar:
            try:
                try:
                    img_mask_alpha = cv2.imread(mask_abspath, cv2.IMREAD_UNCHANGED) # 把alpha通道也读取进来
                    rgba = cv2.split(img_mask_alpha)
                    r, g, b, a = rgba
                except Exception as e:
                    print("打开透明掩膜失败e: ", e)
                    continue
                img_mask = a
                img_mask = (img_mask > 10).astype(np.uint8) * 255
                _, erodedRedMask = self.erode_mask_file(img_mask, kernel_size, toRGBA=True)
                if None == erodedRedMask:
                    print(f"[WARN] {mask_abspath} 处理失败: 腐蚀操作返回None")
                    continue
                cv2.imwrite(mask_abspath, erodedRedMask)

                self.send_progress(pbar, deal_msg = 'erode mask {}'.format(mask_abspath))

            except Exception as e:
                print(f"[WARN] {mask_abspath} 处理失败: {e}")

    """
    封装进度回调, 统一用tqdm回调进度|对于不是循环进度的, 自行输入百分比和描述信息就行
    """
    def send_progress(self, pbar, deal_msg):
        """
        @param: pbar            # tqdm对象
        @param: deal_msg        # 处理的信息
        """
        if self.progress_callback == None:
            print("return")
            return
        deal_percent = (pbar.n / pbar.total) * 100

        if pbar.n + 1 >= pbar.total:
            deal_percent = 100
        self.progress_callback(deal_percent, deal_msg)


    # 读取png图成为mask对象，透明部分黑色（0）其他部分白色（255）
    def convertMaskToRGBA(self, mask):
        """
        mask对象, 透明部分黑色（0）其他部分白色（255）
        :param mask: 二值图对象
        :return: mask对象
        """
        # 二值图转成rgba, 把白色的地方变成红色
        _, mask = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)
        rgba = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGBA)
        rgba[:, :, 0] = 0
        rgba[:, :, 1] = 0
        rgba[:, :, 2] = 255
        rgba[:, :, 3] = mask
        return rgba

    
"""
heic2jpg转换 把source目录下的所有heic转换成jpg
"""
def heic2jpg(source, destination):
    # 检查目标文件是否存在，如果存在则跳过转换
    """
    params: source          "<report_id>"目录
    params: destination     "<report_id>"目录
    """

    onlyfiles =[f for f in os.listdir(source) if os.path.isfile(os.path.join(source, f))]
    if not os.path.exists(destination):
        os.makedirs(destination)
    else:
        print("Output dir already exists")
    for file in onlyfiles:
        (name, ext) = os.path.basename(file).split('.')
        dest = os.path.join(destination, name) + '.jpg'
        # 检查目标文件是否已存在
        if os.path.exists(dest):
            print(f"File {dest} already exists, skipping conversion")
            continue
        
        if ext == 'heic' or ext == 'HEIC':
            sour= os.path.join(source, file)
            f=open(sour,"rb")
            bytesIo=f.read()
            fmt = whatimage.identify_image(bytesIo)
            print("fmt: ", fmt)
            if fmt in ['heic', 'avif']:
                try:
                    i = pyheif.read_heif(bytesIo)
                except pyheif.error.HeifError as e:
                    #raise TypeError from e
                    print("heic 2 jpg error")
            # Extract metadata etc
                for metadata in i.metadata or []:
                    if metadata['type']=='Exif':
                        # do whatever
                        print("EXif")
                # Convert to other file format like jpeg
                s = io.BytesIO()
                print("i.mode: ", i.mode)
                pi = Image.frombytes(
                        mode=i.mode, size=i.size, data=i.data)
                pi1 = pi.convert("RGB")
                pi1.save(dest,quality=95)
            elif fmt == 'jpeg':
                sour= os.path.join(source, file)
                shutil.copyfile(sour,dest)
        elif ext == 'jpg' or ext == 'jpeg':
            sour= os.path.join(source, file)
            shutil.copyfile(sour,dest)


# 给人脸图像的眼睛部分盖上椭圆形的黑色块，用于眼睛脱敏
def drawImgCoverEye(img,points):
    """
    @params:
        img: 输入图像
        points: 68个点的二维坐标
    """
    # 左右眼关键点列表
    eye_points_list = [
        [points[45], points[47], points[49], points[46], points[50], points[48]],  # 左眼
        [points[51], points[53], points[55], points[52], points[56], points[54]]   # 右眼
    ]
     # 放大比例
    width_scale = 1.5   # 控制宽度（长轴）
    height_scale = 4  # 控制高度（短轴）

    print("width_scale: ", width_scale)
    print("height_scale: ", height_scale)

    for eye_points in eye_points_list:
        eye_points = np.array(eye_points, dtype=np.float32)

        # 计算几何中心
        center = np.mean(eye_points, axis=0)
        

        # 估算宽高：计算所有点的x、y范围
        xs = eye_points[:, 0]
        ys = eye_points[:, 1]

        width = (np.max(xs) - np.min(xs)) * width_scale
        height = (np.max(ys) - np.min(ys)) * height_scale

        print(width)
        print(height)

        # 椭圆参数：(中心坐标)、(宽、高)、角度
        ellipse = (tuple(center), (width, height), 0)

        # 画椭圆
        cv2.ellipse(img, ellipse, (0, 0, 0), -1)

    return img

def eyes_masking(img_names, img, point_path):
    # 读取图片
    # 假设你有68个关键点，示例格式如下：
    # points = [[x1, y1], [x2, y2], ..., [x68, y68]]
    # 你需要替换成你实际的68点坐标
    with open(point_path, 'r', encoding='utf-8') as f:
        data = json.loads(f.read())
    points = np.array(data)
    # 左右眼关键点列表
    eye_points_list = [
        [points[45], points[47], points[49], points[46], points[50], points[48]],  # 左眼
        [points[51], points[53], points[55], points[52], points[56], points[54]]   # 右眼
    ]

    print("img_names: ", img_names)
    # 放大比例
    width_scale = 1.5   # 控制宽度（长轴）
    height_scale = 4  # 控制高度（短轴）

    print("width_scale: ", width_scale)
    print("height_scale: ", height_scale)
    
    for eye_points in eye_points_list:
        eye_points = np.array(eye_points, dtype=np.float32)

        # 计算几何中心
        center = np.mean(eye_points, axis=0)
        

        # 估算宽高：计算所有点的x、y范围
        xs = eye_points[:, 0]
        ys = eye_points[:, 1]

        width = (np.max(xs) - np.min(xs)) * width_scale
        height = (np.max(ys) - np.min(ys)) * height_scale

        print(width)
        print(height)

        # 椭圆参数：(中心坐标)、(宽、高)、角度
        ellipse = (tuple(center), (width, height), 0)

        # 画椭圆
        cv2.ellipse(img, ellipse, (0, 0, 0), -1)

    return img
"""
加载矢量五官点-1
"""
def loadVector(report_id, direction):
    """
    @res:
        result_face: True/False
        points: 二维数组
        lm: 格式化的点
    """
    detector = FaceDetectorDelib()
    result_face = False
    lm = []
    points = []
    try:
        with open("{}/vector/{}.txt".format(report_id, direction), 'r') as f:
            points = json.load(f)
        if 0 != len(points):
            result_face = True
        lm = detector.formatDlib(points)
    except Exception as e:
        print("linux下矢量文件{}结果为空! --{}".format(direction, e))
    return result_face, lm, points


# 将多个二值掩码图像合并成一个掩码图像。
def combineMasks(maskImgs):
    """
    将多个二值掩码图像合并成一个掩码图像。

    :param maskImgs: 多个二值掩码图像的列表，格式 [maskimg1, maskimg2, maskimg3]
    :return: 合并之后的掩码图像
    """
    # 检查输入列表是否为空
    if not maskImgs:
        raise ValueError("maskImgs 列表不能为空")
    
    # 获取第一个掩码图像的大小
    first_mask = maskImgs[0]
    if len(first_mask.shape) != 2:
        raise ValueError("所有掩码图像必须是单通道的二值图")
    
    height, width = first_mask.shape
    
    # 创建一个与第一个掩码图像大小相同的空白掩码图像
    combined_mask = np.zeros((height, width), dtype=np.uint8)
    
    # 遍历所有掩码图像并合并
    for mask in maskImgs:
        if mask.shape != (height, width):
            raise ValueError("所有掩码图像的大小必须一致")
        combined_mask = cv2.bitwise_or(combined_mask, mask)
    
    return combined_mask



def drawMaskCombineMask(mask,maskimg):
    """
    在二值图mask上合并一个二值图maskimg。

    :param mask: 二值图mask
    :param maskimg: 二值图maskimg
    :return: 合并后的二值图mask
    """
    # 确保 mask 和 maskimg 都是 numpy 数组
    mask = np.array(mask)
    maskimg = np.array(maskimg)
    
    # 确保 mask 和 maskimg 都是单通道的二值图
    if len(mask.shape) != 2 or len(maskimg.shape) != 2:
        raise ValueError("mask 和 maskimg 必须是单通道的二值图")
    
    # 使用 bitwise_or 进行合并
    combined_mask = cv2.bitwise_or(mask, maskimg)
    
    return combined_mask


def drawMaskByContours(mask, contours, thickness=10):
    """
    在二值图mask上绘制多个轮廓（使用cv2.polylines方式）。
    
    :param mask 二值图mask
    :param contours 多个轮廓
                    格式: [[[x,y],[x,y],[x,y],[x,y]],[[x,y],[x,y],[x,y],[x,y]]]
    :param thickness: 轮廓的线宽
    :return: 二值图mask
    """
    # 遍历每个轮廓并绘制
    for contour in contours:
        # 将轮廓点转换为numpy数组并调整形状为(n,1,2)
        contour_np = np.array(contour, dtype=np.int32).reshape(-1, 1, 2)
        # 使用polylines绘制闭合轮廓
        cv2.polylines(mask, [contour_np], isClosed=True, color=255, thickness=thickness)
    return mask
    

def drawNewMaskByContours(contours,mask_width,mask_height,thickness=10):
    """
    生成一个二值图，并在上面绘制多个轮廓。
    
    :param countors 多个轮廓
                    格式: [[[x,y],[x,y],[x,y],[x,y]],[[x,y],[x,y],[x,y],[x,y]]]
    :mask_width 二值图的宽度
    :mask_height 二值图的高度
    :param thickness: 轮廓的线宽
    :return: 二值图mask
    """
    # 创建一个空白的二值图
    mask = np.zeros((mask_height, mask_width), dtype=np.uint8)
    
    # 在空白图上绘制轮廓
    cv2.drawContours(mask, contours, -1, 255, thickness)
    
    return mask





    

# 在图像上绘制轮廓(填充)
def drawImgWithContours(img, contours, color, thickness=10):
    """
    在图像上绘制多个轮廓。

    :param img: 图像对象 (numpy array)
    :param contours: 轮廓组，包含多个轮廓，每个轮廓是一个x、y坐标数组。
                     格式: [[[x,y],[x,y],[x,y],[x,y]],[[x,y],[x,y],[x,y],[x,y]]]
    :param color: 绘制轮廓的颜色 (B, G, R)
    :param thickness: 轮廓的线宽
    :return: 绘制了轮廓的图像
    """
    # 确保 img 是一个 numpy 数组
    img = np.array(img)
    
    # 创建一个与 img 大小相同的副本，用于绘制轮廓
    result_img = img.copy()
    
    # 绘制轮廓
    cv2.drawContours(result_img, contours, -1, color, thickness)
    
    return result_img

# 读取png图成为mask对象，透明部分黑色（0）其他部分白色（255）
def readMaskFromPng(pngfilename):
    """
    读取png图成为mask对象，透明部分黑色（0）其他部分白色（255）
    :param pngfilename: png文件路径
    :return: mask对象
    """
    # 读取包含Alpha通道的图像
    img = cv2.imread(pngfilename, cv2.IMREAD_UNCHANGED)
    
    # 检查是否包含Alpha通道(通道数为4)
    if img is not None and img.shape[2] == 4:
        # 分离Alpha通道
        _, _, _, alpha = cv2.split(img)
        # 创建二值掩码: 透明区域(alpha=0)设为0，不透明区域设为255
        mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
    else:
        # 若无Alpha通道，使用灰度读取并强制二值化
        mask = cv2.imread(pngfilename, cv2.IMREAD_GRAYSCALE)
        _, mask = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)
    return mask



