# ------------------------------------------------------------------------
# Yuanwen Yue
# ETH Zurich
# ------------------------------------------------------------------------

import copy
import json
import math
import os
import sys
import time
from typing import Iterable

import numpy as np
import random
import MinkowskiEngine as ME
import wandb
import torch

from utils.seg import mean_iou, mean_iou_scene, cal_click_loss_weights, extend_clicks, get_simulated_clicks
import utils.misc as utils
from utils.memory_monitor import print_memory_status, check_memory_safety

from evaluation.evaluator_MO import EvaluatorMO


def train_one_epoch(model: torch.nn.Module, criterion: torch.nn.Module,
                    data_loader: Iterable, optimizer: torch.optim.Optimizer,
                    device: torch.device, epoch: int, train_total_iter: int, max_norm: float = 0):
    model.train()
    criterion.train()
    metric_logger = utils.MetricLogger(delimiter="  ")
    header = 'Epoch: [{}]'.format(epoch)

    print_freq = 10

    for i, batched_inputs in enumerate(metric_logger.log_every(data_loader, print_freq, header)):

        coords, raw_coords, feats, labels, _, _, click_idx, _, _, tf_label = batched_inputs
        coords = coords.to(device)
        labels = [l.to(device) for l in labels]
        labels_new_part = []  # [batch_size][N_points_in_scene]，相当于labels_new_part[idx]中只有参与训练的part上被写了对应的id（从1开始，0是背景）
        labels_new_obj = []  # [batch_size][N_points_in_scene]，相当于labels_new_obj[idx]中只有参与训练的object上被写了对应的id（10/1等）
        selected_object_ids_new = {}  # [batch_size][num_obj]，记录每个场景中参与训练的object_id（10/1等）
        labels_new_shield_part = []
        raw_coords = raw_coords.to(device)
        feats = feats.to(device)
        batch_idx = coords[:,0]

        data = ME.SparseTensor(
                            coordinates=coords,
                            features=feats,
                            device=device
                            )

        pcd_features, aux, coordinates, pos_encodings_pcd = model.forward_backbone(data, raw_coordinates=raw_coords)

        for idx in range(batch_idx.max() + 1):

            sample_mask = batch_idx == idx
            sample_labels = labels[idx] 
            sample_raw_coords = raw_coords[sample_mask]
            valid_part_ids = torch.unique(sample_labels)
            valid_part_ids = valid_part_ids[valid_part_ids != -1]
            object_to_parts = {}

            for part_label in valid_part_ids.tolist():
                object_id = part_label // 100
                if object_id not in object_to_parts:
                    object_to_parts[object_id] = []
                object_to_parts[object_id].append(part_label)
            object_ids = list(object_to_parts.keys())
            object_pesuodo = tf_label[idx]
            object_pesuodo = set(object_to_parts.keys()) & set(object_pesuodo)

            # selected_object_ids = random.sample(object_ids, 1)
            selected_object_ids_new[idx] = 1

            sample_labels_new_part = torch.zeros(sample_labels.shape[0], device=device)
            sample_labels_new_obj = torch.zeros(sample_labels.shape[0], device=device)
            sample_labels_new_shield_part = torch.ones(sample_labels.shape[0], device=device)

            part_num = 1
            all_parts = []
            for obj_id in object_ids:
                all_parts.extend(object_to_parts[obj_id])

            # for i, _ in enumerate(selected_object_ids):
            click_idx[idx][str(1)] = {}
            part_indices_total = []
            click_idx[idx][str(1)]['0'] = []
            num_parts = random.randint(3, 10)
            selected_parts = random.sample(all_parts, num_parts)

            for part_label in selected_parts:
                part_mask = (sample_labels == part_label)
                
                part_indices_total.append(part_mask)
                sample_labels_new_part[part_mask] = part_num
                click_idx[idx][str(1)][str(part_num)] = []
                part_num += 1
            
            shield_parts = [p for p in all_parts if p not in selected_parts]
            for part_label in shield_parts:
                shield_mask = (sample_labels == part_label)
                sample_labels_new_shield_part[shield_mask] = 0

            if len(part_indices_total) > 0:
                obj_indices = torch.cat([pm.nonzero(as_tuple=True)[0] for pm in part_indices_total])
                sample_labels_new_obj[obj_indices] = 1

            click_idx[idx]['0'] = []
            labels_new_part.append(sample_labels_new_part)
            labels_new_obj.append(sample_labels_new_obj)
            labels_new_shield_part.append(sample_labels_new_shield_part)

        click_time_idx = copy.deepcopy(click_idx)


        current_num_iter = 0
        num_forward_iters = random.randint(0, 19)

        with torch.no_grad():
            model.eval()
            eval_model = model

            while current_num_iter <= num_forward_iters:

                if current_num_iter == 0:
                    pred = [torch.zeros(l.shape).to(device) for l in labels_new_part]
                else:
                    has_any_fg = False
                    for b in range(batch_idx.max().item() + 1):
                        if _total_fg_clicks(click_idx[b]) > 0:
                            has_any_fg = True
                            break
                    if has_any_fg:
                        outputs = eval_model.forward_mask(
                            pcd_features, aux, coordinates, pos_encodings_pcd,
                            click_idx=click_idx, click_time_idx=click_time_idx,
                            target_object_id=selected_object_ids_new
                        )

                        if isinstance(outputs, str) and outputs == "ignore this test":
                            pred = [torch.zeros(l.shape, device=device) for l in labels_new_part]
                        else:
                            pred_logits = outputs['part_predictions_mask']
                            pred = [p.argmax(-1) for p in pred_logits]
                    else:
                        pred = [torch.zeros(l.shape, device=device) for l in labels_new_part]


                for idx in range(batch_idx.max() + 1):
                    sample_mask = batch_idx == idx
                    sample_pred = pred[idx]

                    if current_num_iter != 0:

                        for object_id, part_dict in click_idx[idx].items():
                            if object_id == '0':
                                for cids in part_dict:  # 这里假设 cids 是列表
                                    sample_pred[cids] = 0
                                continue
                            for part_id, cids in part_dict.items():
                                sample_pred[cids] = int(part_id)

                    sample_labels = labels_new_part[idx]                # [N_scene_points]
                    sample_labels_shield = labels_new_shield_part[idx]
                    sample_raw_coords = raw_coords[sample_mask]         # [N_scene_points, 3]
                    
                    
                    new_clicks, new_clicks_num, new_click_pos, new_click_time = get_simulated_clicks(
                        sample_pred, sample_labels, sample_raw_coords, sample_labels_shield,
                        current_num_clicks=current_num_iter, training=True,
                    )

                    if new_clicks is not None:
                        click_idx[idx], click_time_idx[idx] = extend_clicks(
                            click_idx[idx], click_time_idx[idx],
                            new_clicks, new_click_time
                        )

                current_num_iter += 1

        #########  3. real forward pass with loss back propagation  #########

        model.train()

        outputs = model.forward_mask(pcd_features, aux, coordinates, pos_encodings_pcd,
                                     click_idx=click_idx, click_time_idx=click_time_idx, target_object_id=selected_object_ids_new)
        # loss
        click_weights = cal_click_loss_weights(coords[:,0], raw_coords, torch.cat(labels_new_part), click_idx)

        loss_dict = criterion(outputs, labels_new_part, click_weights)

        weight_dict = criterion.weight_dict
        losses = sum(loss_dict[k] * weight_dict[k] for k in loss_dict.keys() if k in weight_dict)

        loss_dict_reduced = utils.reduce_dict(loss_dict)
        loss_dict_reduced_unscaled = {f'{k}_unscaled': v
                                    for k, v in loss_dict_reduced.items()}
        loss_dict_reduced_scaled = {k: v * weight_dict[k]
                                    for k, v in loss_dict_reduced.items() if k in weight_dict}
        losses_reduced_scaled = sum(loss_dict_reduced_scaled.values())

        loss_value = losses_reduced_scaled.item()

        if not math.isfinite(loss_value):
            print("Loss is {}, stopping training".format(loss_value))
            print(loss_dict_reduced)
            sys.exit(1)

        train_total_iter+=1

        optimizer.zero_grad()
        losses.backward()
        if max_norm > 0:
            grad_total_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm)
        else:
            grad_total_norm = utils.get_total_grad_norm(model.parameters(), max_norm)
        optimizer.step()

        with torch.no_grad():
            pred_logits = outputs['part_predictions_mask']
            pred = [p.argmax(-1) for p in pred_logits]
            metric_logger.update(mIoU=mean_iou(pred, labels_new_part))

            metric_logger.update(grad_norm=grad_total_norm)
            metric_logger.update(loss=loss_value, **loss_dict_reduced_scaled, **loss_dict_reduced_unscaled)
            metric_logger.update(lr=optimizer.param_groups[0]["lr"])
 

        if ((i + 1) % 100 == 0):
            wandb.log({
                "train/loss": metric_logger.meters['loss'].avg,
                "train/loss_bce": metric_logger.meters['loss_bce'].avg,
                "train/loss_dice": metric_logger.meters['loss_dice'].avg,

                "train/mIoU": metric_logger.meters['mIoU'].avg,
                "train/total_iter": train_total_iter
                })

    # gather the stats from all processes
    metric_logger.synchronize_between_processes()
    print("Averaged stats:", metric_logger)

    return {k: meter.global_avg for k, meter in metric_logger.meters.items()}, train_total_iter


def _total_fg_clicks(click_idx_batch_entry):
    # 统计该样本中所有前景点击数量（不含 '0' 背景）
    total = 0
    for obj_id, part_dict in click_idx_batch_entry.items():
        if obj_id == '0':
            continue
        for _, cids in part_dict.items():
            total += len(cids)
    return total


@torch.no_grad()
def evaluate(model, criterion, data_loader, args, epoch, device):
    model.eval()

    metric_logger = utils.MetricLogger(delimiter="  ")
    header = 'Test:'

    instance_counter = 0
    results_file = os.path.join(args.valResults_dir, 'val_results_epoch_' + str(epoch) + '.csv')
    f = open(results_file, 'w')

    for batched_inputs in metric_logger.log_every(data_loader, 10, header):

        coords, raw_coords, feats, labels, labels_full, inverse_map, click_idx, scene_name, num_obj, tf_label = batched_inputs
        coords = coords.to(device)
        raw_coords = raw_coords.to(device)
        labels = [l.to(device) for l in labels]
        labels_full = [l.to(device) for l in labels_full]
        selected_object_ids_new = {}

        data = ME.SparseTensor(
                                coordinates=coords,
                                features=feats,
                                device=device
                                )

        ###### interactive evaluation ######
        batch_idx = coords[:,0]
        batch_size = batch_idx.max()+1

        click_time_idx = copy.deepcopy(click_idx)
        click_idx = list(click_idx)
        click_time_idx = list(click_time_idx)
        current_num_clicks = 0

        # pre-compute backbone features only once
        pcd_features, aux, coordinates, pos_encodings_pcd = model.forward_backbone(data, raw_coordinates=raw_coords)
        num_part = []
        for idx in range(batch_idx.max()+1):
            part_num = 0
            for obj_id, click_dict in click_idx[idx].items():
                if obj_id == '0':
                    continue
                for click_id, click_indices in click_dict.items():
                    part_num += 1
            num_part.append(part_num)

        max_part_num = max(num_part)

        # Use the first scene's part_num for max_num_clicks calculation
        max_num_clicks = max_part_num * args.max_num_clicks

        for idx in range(batch_idx.max()+1):
            selected_object_ids_new[idx] = 1

        while current_num_clicks <= max_num_clicks:
            if current_num_clicks == 0:
                pred = [torch.zeros(l.shape).to(device) for l in labels]
            else:
                outputs = model.forward_mask(pcd_features, aux, coordinates, pos_encodings_pcd,
                                             click_idx=click_idx, click_time_idx=click_time_idx, target_object_id=selected_object_ids_new)
                if outputs == "ignore this test":
                    print("bad test")
                    break
                pred_logits = outputs['part_predictions_mask']
                pred = [p.argmax(-1) for p in pred_logits]

            # if current_num_clicks != 0:
            #     click_weights = cal_click_loss_weights(batch_idx, raw_coords, torch.cat(labels), click_idx)
            #     loss_dict = criterion(outputs, labels, click_weights)
            #     weight_dict = criterion.weight_dict
            #     losses = sum(loss_dict[k] * weight_dict[k] for k in loss_dict.keys() if k in weight_dict)

            #     loss_dict_reduced = utils.reduce_dict(loss_dict)
            #     loss_dict_reduced_scaled = {k: v * weight_dict[k]
            #                                 for k, v in loss_dict_reduced.items() if k in weight_dict}
            #     loss_dict_reduced_unscaled = {f'{k}_unscaled': v
            #                                 for k, v in loss_dict_reduced.items()}

            updated_pred = []
            # print("range(batch_idx.max()+1)",batch_idx.max()+1)
            for idx in range(batch_idx.max()+1):
                sample_mask = batch_idx == idx
                sample_pred = pred[idx]

                sample_mask = sample_mask.to(feats.device)  # Move sample_mask to the same device as feats
                sample_feats = feats[sample_mask]

                if current_num_clicks != 0:
                    # update prediction with sparse gt
                    for object_id, part_dict in click_idx[idx].items():
                        if object_id == '0':
                            for cids in part_dict:  # 这里假设 cids 是列表
                                sample_pred[cids] = 0
                            continue
                        for part_id, cids in part_dict.items():
                            sample_pred[cids] = int(part_id)
                    updated_pred.append(sample_pred)

                sample_labels = labels[idx]
                sample_raw_coords = raw_coords[sample_mask]
                sample_pred_full = sample_pred[inverse_map[idx]]

                sample_labels_full = labels_full[idx]
                sample_iou, _ = mean_iou_scene(sample_pred_full, sample_labels_full)
                
                line = str(instance_counter+idx) + ' ' + scene_name[idx] + ' ' + str(num_part[idx]) + ' ' + str(current_num_clicks/num_part[idx]) + ' ' + str(
                sample_iou.cpu().numpy()) + '\n'
                f.write(line)

                # print(scene_name[idx], 'Object: ', num_obj[idx], 'num clicks: ', current_num_clicks/num_obj[idx], 'IOU: ', sample_iou.item())
                print(scene_name[idx], 'Part: ', num_part[idx], 'num clicks: ', current_num_clicks/num_part[idx], 'IOU: ', sample_iou.item())
                new_clicks, new_clicks_num, new_click_pos, new_click_time = get_simulated_clicks(sample_pred, sample_labels, sample_raw_coords, labels_shield_qv=None, current_num_clicks=current_num_clicks, training=False)
                # print("new_clicks:",new_clicks)
                ### add new clicks ###
                if new_clicks is not None:
                    click_idx[idx], click_time_idx[idx] = extend_clicks(click_idx[idx], click_time_idx[idx], new_clicks, new_click_time)

            # if current_num_clicks != 0:
            #     metric_logger.update(mIoU=mean_iou(updated_pred, labels))
            #     metric_logger.update(loss=sum(loss_dict_reduced_scaled.values()),
            #                         **loss_dict_reduced_scaled,
            #                         **loss_dict_reduced_unscaled)

            if current_num_clicks == 0:
                new_clicks_num = num_part[idx]
                # print("New clicks num:", new_clicks_num)
                pass
            else:
                new_clicks_num = 1
            current_num_clicks += new_clicks_num
            print("current_num_clicks:", current_num_clicks)

        instance_counter += len(num_obj)
        # instance_counter += batch_size

    f.close()
    evaluator = EvaluatorMO(args.val_list, results_file, [0.5,0.65,0.8,0.85,0.9], args.max_num_clicks)
    results_dict = evaluator.eval_results()

    # gather the stats from all processes
    metric_logger.synchronize_between_processes()
    print("Averaged stats:", metric_logger)

    stats = {k: meter.global_avg for k, meter in metric_logger.meters.items()}
    stats.update(results_dict)

    return stats
