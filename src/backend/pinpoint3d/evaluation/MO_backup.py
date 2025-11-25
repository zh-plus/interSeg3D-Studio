import numpy as np
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np
import json
import os
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
        # objects = {}
        # scenes = {}
        valid_scene_parts = set()
        for ii in dataset_.keys():
        #     scenes[ii.replace('scene','')]=1
        # print('number of scenes kept: ',len(scenes))
        #     objects[ii.replace('scene','').replace('obj_','')]=1
        # print('number of objects kept: ',len(objects))
            scene_name = ii.replace('scene','')
            valid_scene_parts.add(scene_name)
        print('number of scenes kept: ',len(valid_scene_parts))

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
                # if len(splits) < 5:
                #     print(f"DEBUG: Line {line_count} has insufficient splits: {splits}")
                #     continue
                    
                scene_name = splits[1].replace('scene','')
                # object_id = splits[2]
                part_id = splits[2]
                num_clicks = splits[3] # 每个part的点击次数
                iou = splits[4]
                
                # # Debug first few lines
                # if line_count <= 5:
                #     print(f"DEBUG: Line {line_count}: scene={scene_name}, part={part_id}, clicks={num_clicks}, IoU={iou}")

                # if (scene_name + '_' + object_id) in objects:
                #     if (scene_name + '_' + object_id) not in all_object:
                #         all_object[(scene_name + '_' + object_id)]=1
                #         all[(scene_name + '_' + object_id)]=[]
                #     all[(scene_name + '_' + object_id)].append((num_clicks,iou))
                # if scene_name in scenes:  # 只检查scene是否在评估列表中
                #     if scene_name not in all_scenes:
                #         all_scenes[scene_name]=1
                #         all[scene_name]=[]
                #     all[scene_name].append((num_clicks,iou))
                # Check if this scene is in our valid scenes list
                if scene_name in valid_scene_parts:
                    scene_part_key = f"{scene_name}_{part_id}"
                    if scene_part_key not in all_scene_parts:
                        all_scene_parts[scene_part_key] = 1
                        all[scene_part_key] = []
                    all[scene_part_key].append((num_clicks, iou))
                    
                    # Debug: print some data to see what's happening
                    if scene_part_key in ['00036_01', '00091_01']:  # Debug specific scenes
                        print(f"DEBUG: {scene_part_key} - clicks: {num_clicks}, IoU: {iou}, MAX_IOU: {MAX_IOU}")
                else:
                    # Debug: print why scenes are not being processed
                    if scene_name in ['00036', '00091']:
                        print(f"DEBUG: {scene_name} not in valid_scene_parts: {valid_scene_parts}")

                    if float(iou)>=MAX_IOU:
                        # if (scene_name+'_'+object_id) not in results_dict_KatIOU:
                        #     results_dict_KatIOU[scene_name+'_'+object_id]=float(num_clicks)
                        #     num_objects+=1
                        # if scene_name not in results_dict_KatIOU:
                        #     results_dict_KatIOU[scene_name]=float(num_clicks)
                        #     num_parts+=1
                        if scene_part_key not in results_dict_KatIOU:
                            results_dict_KatIOU[scene_part_key] = float(num_clicks)
                            num_parts += 1
                            ordered_clicks.append(float(num_clicks))
                            print(f"SUCCESS: {scene_part_key} reached IoU {iou} >= {MAX_IOU} with {num_clicks} clicks")

                    elif float(num_clicks)>=float(self.max_num_clicks) and (float(iou)>=0):
                        # if (scene_name+'_'+object_id) not in results_dict_KatIOU:
                        #     results_dict_KatIOU[scene_name+'_'+object_id] = float(num_clicks)
                        #     num_objects += 1
                        # if scene_name not in results_dict_KatIOU:
                        #     results_dict_KatIOU[scene_name] = float(num_clicks)
                        if scene_part_key not in results_dict_KatIOU:
                            results_dict_KatIOU[scene_part_key] = float(num_clicks)
                            num_parts += 1
                            ordered_clicks.append(float(num_clicks))
                            print(f"MAX_CLICKS: {scene_part_key} reached max clicks {num_clicks} with IoU {iou}")

                    results_dict_per_click.setdefault(num_clicks, 0)
                    results_dict_per_click_iou.setdefault(num_clicks, 0)

                    results_dict_per_click[num_clicks]+=1
                    results_dict_per_click_iou[num_clicks]+=float(iou)
                else:
                    #print(scene_name + '_' + object_id)
                    pass
                    
        if len(results_dict_KatIOU.values())==0:
            print('no parts to eval')
            return [], 0, 0, {}, {}


        click_at_IoU =sum(results_dict_KatIOU.values())/len(results_dict_KatIOU.values())
        print('click@', MAX_IOU, click_at_IoU, num_parts, len(results_dict_KatIOU.values()))


        return ordered_clicks, sum(results_dict_KatIOU.values()), len(results_dict_KatIOU.values()), results_dict_per_click_iou, results_dict_per_click 


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
        expected_clicks = ['1.0', '3.0', '5.0']  # Add more if needed
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
            # 'NoC@50': sum(NOC[0.5])/sum(NOO[0.5]),
            # 'NoC@65': sum(NOC[0.65])/sum(NOO[0.65]),
            # 'NoC@80': sum(NOC[0.8])/sum(NOO[0.8]),
            # 'NoC@85': sum(NOC[0.85])/sum(NOO[0.85]),
            # 'NoC@90': sum(NOC[0.9])/sum(NOO[0.9]),
            # 'IoU@1': IOU_PER_CLICK_dict['1.0']/NOO_PER_CLICK_dict['1.0'],
            # 'IoU@3': IOU_PER_CLICK_dict['3.0']/NOO_PER_CLICK_dict['3.0'],
            # 'IoU@5': IOU_PER_CLICK_dict['5.0']/NOO_PER_CLICK_dict['5.0'],
            # # 'IoU@10': IOU_PER_CLICK_dict['10.0']/NOO_PER_CLICK_dict['10.0'],
            # # 'IoU@15': IOU_PER_CLICK_dict['15.0']/NOO_PER_CLICK_dict['15.0']
            'NoC@50': safe_divide(sum(NOC[0.5]), sum(NOO[0.5]), default=float('inf')),
            'NoC@65': safe_divide(sum(NOC[0.65]), sum(NOO[0.65]), default=float('inf')),
            'NoC@80': safe_divide(sum(NOC[0.8]), sum(NOO[0.8]), default=float('inf')),
            'NoC@85': safe_divide(sum(NOC[0.85]), sum(NOO[0.85]), default=float('inf')),
            'NoC@90': safe_divide(sum(NOC[0.9]), sum(NOO[0.9]), default=float('inf')),
            'IoU@1': safe_divide(IOU_PER_CLICK_dict.get('1.0', 0), NOO_PER_CLICK_dict.get('1.0', 0), default=0.0),
            'IoU@3': safe_divide(IOU_PER_CLICK_dict.get('3.0', 0), NOO_PER_CLICK_dict.get('3.0', 0), default=0.0),
            'IoU@5': safe_divide(IOU_PER_CLICK_dict.get('5.0', 0), NOO_PER_CLICK_dict.get('5.0', 0), default=0.0),
            # 'IoU@10': safe_divide(IOU_PER_CLICK_dict.get('10.0', 0), NOO_PER_CLICK_dict.get('10.0', 0), default=0.0),
            # 'IoU@15': safe_divide(IOU_PER_CLICK_dict.get('15.0', 0), NOO_PER_CLICK_dict.get('15.0', 0), default=0.0)
        }
        print('****************************')
        print(results_dict)
        
        # Print debug information
        print('Debug Info:')
        print('NOC:', NOC)
        print('NOO:', NOO)
        print('IOU_PER_CLICK_dict:', IOU_PER_CLICK_dict)
        print('NOO_PER_CLICK_dict:', NOO_PER_CLICK_dict)

        return results_dict
