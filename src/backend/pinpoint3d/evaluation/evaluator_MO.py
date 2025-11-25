import numpy as np
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np
import json
import os
import torch
"""
Evaluator for interactive multi-object segmentation
每个物体在给定次数下的IoU，以及达到指定IoU所需的点击次数
"""
class EvaluatorMO():


    def __init__(
        self,
        scene_list_file,
        result_file,
        MAX_IOU,
        max_num_clicks
        ):

        self.MAX_IOU = MAX_IOU

        with open(scene_list_file) as json_file:
            self.dataset_list = json.load(json_file)

        self.result_file = result_file
        self.max_num_clicks = max_num_clicks

    def eval_per_class(self, MAX_IOU=0.8, dataset_=None):
        #NoC@X = (达到IoU≥X的所有part的总点击数) / (达到IoU≥X的part总数量)
        # objects = {}
        # scenes = {}
        valid_scene_parts = set()
        for ii in dataset_.keys():
            # Extract the base scene name (e.g., '00104' from 'scene_00104_08_obj_1')
            # print("for ii in dataset_.keys():", ii)
            scene_name = ii.replace('scene_','')  # Only take the first part before any underscore
            # scene_name = scene_name.replace('_obj_1','')
            scene_name = scene_name.split('_obj_')[0]
            valid_scene_parts.add(scene_name)
        # print('number of scenes kept: ',len(valid_scene_parts))
        # print('DEBUG: First few valid scenes:', list(valid_scene_parts)[:5])

        results_dict_KatIOU = {}
        # num_objects = 0
        num_parts = 0
        ordered_clicks = []

        # all_object={}
        # all_scenes={}
        all_scene_parts = {}
        results_dict_per_click = {}
        results_dict_per_click_iou = {}
        all = {}
        # print(f"DEBUG: Opening result file: {self.result_file}")
        with open(self.result_file, 'r') as f:
            # line_count = 0
            while True:
                line = f.readline()
                if not line:
                    break
                # line_count += 1
                splits = line.rstrip().split(' ')
                # Skip empty lines or lines with insufficient fields
                if len(splits) < 5:
                    print(f"WARNING: Line has insufficient fields: {splits} (length: {len(splits)})")
                    continue
                    
                scene_name = splits[1].replace('scene_','')  # Remove the leading underscore
                part_id = splits[2]
                num_clicks = splits[3] # 每个part的点击次数
                iou = splits[4]
                
                # Check if this scene is in our valid scenes list
                print(scene_name)
                if scene_name in valid_scene_parts:
                    scene_part_key = f"{scene_name}_{part_id}"
                    if scene_part_key not in all_scene_parts:
                        all_scene_parts[scene_part_key] = 1
                        all[scene_part_key] = []
                    all[scene_part_key].append((num_clicks, iou))
                    
                    if float(iou)>=MAX_IOU:
                        if scene_part_key not in results_dict_KatIOU:
                            results_dict_KatIOU[scene_part_key] = float(num_clicks)
                            num_parts += 1
                            ordered_clicks.append(float(num_clicks))
                            # print(f"SUCCESS: {scene_part_key} reached IoU {iou} >= {MAX_IOU} with {num_clicks} clicks")

                    elif float(num_clicks)>=float(self.max_num_clicks) and (float(iou)>=0):
                        if scene_part_key not in results_dict_KatIOU:
                            results_dict_KatIOU[scene_part_key] = float(num_clicks)
                            num_parts += 1
                            ordered_clicks.append(float(num_clicks))
                            # print(f"MAX_CLICKS: {scene_part_key} reached max clicks {num_clicks} with IoU {iou}")

                    results_dict_per_click.setdefault(num_clicks, 0)
                    results_dict_per_click_iou.setdefault(num_clicks, 0)

                    results_dict_per_click[num_clicks]+=1
                    results_dict_per_click_iou[num_clicks]+=float(iou)
                else:
                    pass

        if len(results_dict_KatIOU.values())==0:
            print('no parts to eval')
            return [], 0, 0, {}, {}


        click_at_IoU =sum(results_dict_KatIOU.values())/len(results_dict_KatIOU.values())
        print('click@', MAX_IOU, click_at_IoU, num_parts, len(results_dict_KatIOU.values()))


        return ordered_clicks, sum(results_dict_KatIOU.values()), len(results_dict_KatIOU.values()), results_dict_per_click_iou, results_dict_per_click 


    def calculate_ap_metrics(self, iou_thresholds=None):
        """
        计算AP (Average Precision) 指标
        AP@[0.5:0.95] 类似于COCO评估标准
        """
        if iou_thresholds is None:
            # 使用COCO标准的IoU阈值
            iou_thresholds = np.arange(0.5, 1.0, 0.05)  # [0.5, 0.55, 0.6, ..., 0.95]
        
        ap_results = {}
        precision_per_threshold = []
        
        print(f"=== Calculating AP metrics across {len(iou_thresholds)} IoU thresholds ===")
        
        for iou_threshold in iou_thresholds:
            # 计算在该IoU阈值下的精度
            _, total_clicks, total_parts, _, _ = self.eval_per_class(iou_threshold, self.dataset_list)
            
            if total_parts > 0:
                # 精度 = 达到目标IoU的part数量 / 总part数量
                precision = total_parts / len(self.dataset_list)
                precision_per_threshold.append(precision)
                print(f"IoU@{iou_threshold:.2f}: Precision = {precision:.4f} ({total_parts} parts)")
            else:
                precision_per_threshold.append(0.0)
                print(f"IoU@{iou_threshold:.2f}: Precision = 0.0000 (0 parts)")
        
        # 计算AP指标
        ap_results.update({
            'AP@[0.5:0.95]': np.mean(precision_per_threshold),  # 整体AP
            'AP@0.5': precision_per_threshold[0] if len(precision_per_threshold) > 0 else 0.0,  # AP@IoU=0.5
            'AP@0.75': precision_per_threshold[5] if len(precision_per_threshold) > 5 else 0.0,  # AP@IoU=0.75
            'mAP': np.mean(precision_per_threshold),  # mean Average Precision
        })
        
        # 添加详细的precision数组
        ap_results['precision_per_threshold'] = precision_per_threshold
        ap_results['iou_thresholds'] = iou_thresholds.tolist()
        
        return ap_results

    def calculate_ap_with_confidence(self):
        """
        基于置信度的AP计算（如果有预测置信度的话）
        这里用IoU作为置信度的代理
        """
        # 收集所有预测结果
        all_predictions = []
        
        with open(self.result_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                splits = line.rstrip().split(' ')
                if len(splits) < 5:
                    continue
                    
                scene_name = splits[1].replace('scene_','')
                part_id = splits[2]
                num_clicks = float(splits[3])
                iou = float(splits[4])
                
                scene_part_key = f"{scene_name}_{part_id}"
                
                all_predictions.append({
                    'scene_part': scene_part_key,
                    'confidence': iou,  # 使用IoU作为置信度
                    'clicks': num_clicks,
                    'iou': iou
                })
        
        # 按置信度排序
        all_predictions.sort(key=lambda x: x['confidence'], reverse=True)
        
        # 计算不同IoU阈值下的AP
        ap_at_different_iou = {}
        iou_thresholds = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
        
        for iou_thresh in iou_thresholds:
            precision_curve = []
            recall_curve = []
            
            tp = 0  # True Positive
            fp = 0  # False Positive
            total_positives = sum(1 for pred in all_predictions if pred['iou'] >= iou_thresh)
            
            for i, pred in enumerate(all_predictions):
                if pred['iou'] >= iou_thresh:
                    tp += 1
                else:
                    fp += 1
                    
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / total_positives if total_positives > 0 else 0
                
                precision_curve.append(precision)
                recall_curve.append(recall)
            
            # 计算AP (积分)
            ap = np.trapz(precision_curve, recall_curve) if len(recall_curve) > 1 else 0
            ap_at_different_iou[f'AP@{iou_thresh}'] = ap
        
        # 计算mAP
        ap_at_different_iou['mAP'] = np.mean(list(ap_at_different_iou.values()))
        
        return ap_at_different_iou






    def eval_results(self):
        print('--------- Evaluating -----------')
        NOC = {}
        NOO = {}

        # line = str(instance_counter+idx) + ' ' + scene_name[idx].replace('scene','') + ' ' + str(num_part[idx]) + ' ' + str(current_num_clicks/num_part[idx]) + ' ' + str(
        #         sample_iou.cpu().numpy()) + '\n'
        # 0 0682_00 1 11.0 0.23809525
      
        for iou_max in self.MAX_IOU:
            NOC[iou_max] = []
            NOO[iou_max] = []
            IOU_PER_CLICK_dict = None
            NOO_PER_CLICK_dict = None

            result = self.eval_per_class(iou_max, self.dataset_list)
            if isinstance(result, tuple) and len(result) == 5:
                _, noc_perclass, noo_perclass, iou_per_click, noo_per_click = result
                NOC[iou_max].append(noc_perclass)
                NOO[iou_max].append(noo_perclass)
            else:
                print(f"Warning: eval_per_class returned unexpected result for IoU {iou_max}: {result}")
                # Use default values
                noc_perclass, noo_perclass = 0, 0
                iou_per_click, noo_per_click = {}, {}
                NOC[iou_max].append(noc_perclass)
                NOO[iou_max].append(noo_perclass)

            if IOU_PER_CLICK_dict == None:
                IOU_PER_CLICK_dict = iou_per_click
            else:
                # for k in IOU_PER_CLICK_dict.keys():
                for k in iou_per_click.keys():
                    if k not in IOU_PER_CLICK_dict:
                        IOU_PER_CLICK_dict[k] = 0
                    IOU_PER_CLICK_dict[k] += iou_per_click[k]

            if NOO_PER_CLICK_dict == None:
                NOO_PER_CLICK_dict = noo_per_click
            else:
                # for k in NOO_PER_CLICK_dict.keys():
                for k in noo_per_click.keys():
                    if k not in NOO_PER_CLICK_dict:
                        NOO_PER_CLICK_dict[k] = 0
                    NOO_PER_CLICK_dict[k] += noo_per_click[k]


        # Initialize dictionaries with default values for all possible click counts
        expected_clicks = ['1.0','2.0', '3.0', '5.0']  # Add more if needed
        for click_count in expected_clicks:
            if click_count not in IOU_PER_CLICK_dict:
                IOU_PER_CLICK_dict[click_count] = 0
            if click_count not in NOO_PER_CLICK_dict:
                NOO_PER_CLICK_dict[click_count] = 0
        
        # Safe division to avoid division by zero
        def safe_divide(numerator, denominator, default=0.0):
            if denominator == 0:
                return default
            return numerator / denominator
        
        results_dict = {
            'NoC@50': safe_divide(sum(NOC[0.5]), sum(NOO[0.5]), default=float('inf')),
            'NoC@65': safe_divide(sum(NOC[0.65]), sum(NOO[0.65]), default=float('inf')),
            'NoC@80': safe_divide(sum(NOC[0.8]), sum(NOO[0.8]), default=float('inf')),
            'NoC@85': safe_divide(sum(NOC[0.85]), sum(NOO[0.85]), default=float('inf')),
            'NoC@90': safe_divide(sum(NOC[0.9]), sum(NOO[0.9]), default=float('inf')),
            'IoU@1': safe_divide(IOU_PER_CLICK_dict.get('1.0', 0), NOO_PER_CLICK_dict.get('1.0', 0), default=0.0),
            'IoU@2': safe_divide(IOU_PER_CLICK_dict.get('2.0', 0), NOO_PER_CLICK_dict.get('2.0', 0), default=0.0),
            'IoU@3': safe_divide(IOU_PER_CLICK_dict.get('3.0', 0), NOO_PER_CLICK_dict.get('3.0', 0), default=0.0),
            'IoU@5': safe_divide(IOU_PER_CLICK_dict.get('5.0', 0), NOO_PER_CLICK_dict.get('5.0', 0), default=0.0),
            # 'IoU@10': safe_divide(IOU_PER_CLICK_dict.get('10.0', 0), NOO_PER_CLICK_dict.get('10.0', 0), default=0.0),
            # 'IoU@15': safe_divide(IOU_PER_CLICK_dict.get('15.0', 0), NOO_PER_CLICK_dict.get('15.0', 0), default=0.0)
        }
        print('****************************')
        print(results_dict)

        return results_dict
