# ------------------------------------------------------------------------
# Yuanwen Yue
# ETH Zurich
# ------------------------------------------------------------------------
import torch
import numpy as np
import random


def mean_iou_single(pred, labels):
    """Calculate the mean IoU for a single object
    """
    truepositive = pred*labels
    intersection = torch.sum(truepositive==1)
    uni = torch.sum(pred==1) + torch.sum(labels==1) - intersection

    iou = intersection/uni
    return iou

def mean_iou(pred, labels):
    """Calculate the mean IoU for a batch
    """
    assert len(pred) == len(labels)
    bs = len(pred)
    iou_batch = 0.0
    for b in range(bs):
        pred_sample = pred[b]
        labels_sample = labels[b]
        obj_ids = torch.unique(labels_sample)
        obj_ids = obj_ids[obj_ids!=0]
        obj_num = len(obj_ids)
        iou_sample = 0.0
        for obj_id in obj_ids:
            obj_iou = mean_iou_single(pred_sample==obj_id, labels_sample==obj_id)
            iou_sample += obj_iou

        iou_sample /= obj_num

        iou_batch += iou_sample
    
    iou_batch /= bs
    return iou_batch

def mean_iou_scene(pred, labels):
    """
    Calculate the mean IoU for all target objects in the scene.
    - labels 中 0 视为背景，不计入
    返回: (scene_mean_iou: torch.Tensor, iou_dict: dict[int -> float])
    """
    device = pred.device if torch.is_tensor(pred) else None

    # 先定义，避免提前 return 时未定义
    iou_dict = {}

    # 非零对象
    obj_ids = torch.unique(labels)
    obj_ids = obj_ids[obj_ids != 0]
    obj_num = int(obj_ids.numel())

    # 空场景：直接返回 0.0 和空字典
    if obj_num == 0:
        zero = torch.tensor(0.0, device=device) if device is not None else torch.tensor(0.0)
        return zero, iou_dict

    # 用 tensor 在同一 device 上累加
    iou_sum = torch.tensor(0.0, device=device) if device is not None else torch.tensor(0.0)

    for oid in obj_ids:
        gt_mask = (labels == oid)
        pd_mask = (pred   == oid)

        obj_iou = mean_iou_single(pd_mask, gt_mask)  # 可为 float 或 tensor

        # 记入 dict（转 float）
        if torch.is_tensor(obj_iou):
            iou_dict[int(oid.item())] = float(obj_iou.detach().cpu().item())
            iou_sum = iou_sum + obj_iou
        else:
            iou_dict[int(oid.item())] = float(obj_iou)
            iou_sum = iou_sum + (torch.tensor(obj_iou, device=device) if device is not None
                                 else torch.tensor(obj_iou))

    scene_mean_iou = iou_sum / obj_num
    return scene_mean_iou, iou_dict

# def mean_iou_scene(pred, labels):
#     """Calculate the mean IoU for all target objects in the scene
#     """
#     obj_ids = torch.unique(labels)
#     obj_ids = obj_ids[obj_ids!=0]
#     obj_num = len(obj_ids)
#     iou_sample = 0.0
#     iou_dict = {}
#     for obj_id in obj_ids:
#         obj_iou = mean_iou_single(pred==obj_id, labels==obj_id)
#         iou_dict[int(obj_id)] = float(obj_iou)
#         iou_sample += obj_iou

#     # iou_sample /= obj_num
#     # 加权求IoU
#     # obj_ids = torch.unique(labels)
#     # obj_ids = obj_ids[obj_ids!=0]
#     # total_points = len(labels)
#     # iou_sample = 0.0
#     # total_weight = 0
#     # iou_dict = {}
#     # for obj_id in obj_ids:
#     #     mask_gt = (labels == obj_id)
#     #     obj_points = mask_gt.sum().item()
#     #     weight = obj_points / total_points
#     #     obj_iou = mean_iou_single(pred == obj_id, mask_gt)
#     #     iou_dict[int(obj_id)] = float(obj_iou)
#     #     iou_sample += obj_iou * weight
#     #     total_weight += weight
#     # iou_sample /= total_weight

#     # mask = labels!=0
#     # iou_dict = {}
#     # obj_iou = mean_iou_single(pred[mask], labels[mask])


#     return obj_iou, iou_dict


def loss_weights(points, clicks, tita, alpha, beta):
    """Points closer to clicks have bigger weights. Vice versa.
    """
    pairwise_distances = torch.cdist(points, clicks)
    pairwise_distances, _ = torch.min(pairwise_distances, dim=1)
    # alpha=0.8   beta=2   tita=0.3
    weights = alpha + (beta-alpha) * (1 - torch.clamp(pairwise_distances, max=tita)/tita)

    return weights


def cal_click_loss_weights(batch_idx, raw_coords, labels, click_idx, alpha=0.8, beta=2.0, tita=0.3):
    """Calculate the loss weights for each point in the point cloud.
    """
    weights = []
  
    bs = batch_idx.max() + 1
    for i in range(bs):
        
        click_idx_sample = click_idx[i]
        sample_mask = batch_idx == i
        raw_coords_sample = raw_coords[sample_mask]

        all_click_idx = []
        all_click_idx.extend(click_idx_sample.get('0', []))

        for obj_id, part_dict in click_idx_sample.items():
            if obj_id == '0':
                continue
            for part_id, click_indices in part_dict.items():
                all_click_idx.extend(click_indices)
                
        if len(all_click_idx) == 0:
            weights.append(raw_coords_sample.new_zeros(raw_coords_sample.size(0)))
            continue

        click_points_sample = raw_coords_sample[all_click_idx]
        weights_sample = loss_weights(raw_coords_sample, click_points_sample, tita, alpha, beta)
        weights.append(weights_sample)

    return weights

def loss_weights_iter(points, clicks, click_iter, base_tita, alpha, beta, k=0.3, lambda_t=0.2):
    """Points closer to clicks have bigger weights. Vice versa.
    base_tita=0.3, alpha=0.8, beta=2.0, k=0.3, lambda_t=0.2
    """
    N = points.shape[0]
    M = clicks.shape[0]
    click_iter = torch.tensor(click_iter, device=points.device)

    # 每个点到每个click的距离
    dists = torch.cdist(points, clicks)  # [N, M]

    # 每个click根据时间生成半径（越早，半径越大）
    tita_click = base_tita / (1 + k * click_iter.float())  # [M]

    # expand到[N, M]以用于广播
    tita_matrix = tita_click.unsqueeze(0).expand(N, M)  # [N, M]

    # 归一化距离，截断最大为1（超过作用范围视为最低权重）
    norm_dist = torch.clamp(dists / tita_matrix, max=1.0)  # [N, M]

    # 基于距离计算每个click对每个点的影响（越近越大）
    spatial_weights = alpha + (beta - alpha) * (1 - norm_dist)  # [N, M]

    # 每个click的时间权重（越早越大）
    time_weights = torch.exp(-lambda_t * click_iter.float())  # [M]
    time_weights = time_weights.unsqueeze(0).expand(N, M)  # [N, M]

    # 融合空间+时间权重
    total_weights = spatial_weights * time_weights  # [N, M]

    # 每个点取所有click对它的最大影响力
    final_weights, _ = torch.max(total_weights, dim=1)  # [N]

    return final_weights

def cal_click_loss_weights_iter(batch_idx, raw_coords, labels, click_idx, click_time_idx, alpha=1.2, beta=3.0, tita=0.3):
    """Calculate the loss weights for each point in the point cloud.
    """
    weights = []
  
    bs = batch_idx.max() + 1
    for i in range(bs):
        
        click_idx_sample = click_idx[i]
        sample_mask = batch_idx == i
        raw_coords_sample = raw_coords[sample_mask]

        all_click_idx = []
        all_click_idx.extend(click_idx_sample.get('0', []))

        for obj_id, part_dict in click_idx_sample.items():
            if obj_id == '0':
                continue
            for part_id, click_indices in part_dict.items():
                all_click_idx.extend(click_indices)
        
        click_idx_sample_iter = click_time_idx[i]
        all_click_idx_iter = []
        all_click_idx_iter.extend(click_idx_sample_iter.get('0', []))
        for obj_id, part_dict in click_idx_sample_iter.items():
            if obj_id == '0':
                continue
            for part_id, click_iter_indices in part_dict.items():
                all_click_idx_iter.extend(click_iter_indices)
        # print("all_click_idx:",len(all_click_idx))
        # print("all_click_idx_iter:",len(all_click_idx_iter))
        click_points_sample = raw_coords_sample[all_click_idx]
        weights_sample = loss_weights_iter(raw_coords_sample, click_points_sample, all_click_idx_iter, tita, alpha, beta)
        weights.append(weights_sample)

    return weights


# 原版
# def cal_click_loss_weights(batch_idx, raw_coords, labels, click_idx, alpha=0.8, beta=2.0, tita=0.3):
#     """Calculate the loss weights for each point in the point cloud.
#     """
#     weights = []

#     bs = batch_idx.max() + 1
#     for i in range(bs):
        
#         click_idx_sample = click_idx[i]
#         sample_mask = batch_idx == i
#         raw_coords_sample = raw_coords[sample_mask]
#         all_click_idx = [np.array(v) for k,v in click_idx_sample.items()]
#         all_click_idx = np.hstack(all_click_idx).astype(np.int64).tolist()
#         click_points_sample = raw_coords_sample[all_click_idx]
#         weights_sample = loss_weights(raw_coords_sample, click_points_sample, tita, alpha, beta)
#         weights.append(weights_sample)

#     return weights


def get_next_click_coo_torch(discrete_coords, unique_labels, gt, pred, pairwise_distances):
    """Sample the next click from the center of the error region
    """
    zero_indices = (unique_labels == 0)
    one_indices = (unique_labels == 1)
    if zero_indices.sum() == 0 or one_indices.sum() == 0:
        return None, None, None, -1, None, None

    # point furthest from border
    center_id = torch.where(pairwise_distances == torch.max(pairwise_distances, dim=0)[0])
    center_coo = discrete_coords[one_indices, :][center_id[0][0]]
    center_label = gt[one_indices][center_id[0][0]]
    center_pred = pred[one_indices][center_id[0][0]]

    local_mask = torch.zeros(pairwise_distances.shape[0], device=discrete_coords.device)
    global_id_mask = torch.zeros(discrete_coords.shape[0], device=discrete_coords.device)
    local_mask[center_id] = 1
    global_id_mask[one_indices] = local_mask
    center_global_id = torch.argwhere(global_id_mask)[0][0]

    candidates = discrete_coords[one_indices, :]

    max_dist = torch.max(pairwise_distances)

    return center_global_id, center_coo, center_label, max_dist, candidates

def get_next_simulated_click_multi(error_cluster_ids, error_cluster_ids_mask, pred_qv, labels_qv, coords_qv, error_distances):
    """Sample the next clicks for each error region
    """

    click_dict = {}
    new_click_pos = {}
    click_time_dict = {}
    click_order = 0

    random.shuffle(error_cluster_ids)

    for cluster_id in error_cluster_ids:

        error = error_cluster_ids_mask == cluster_id

        pair_distances = error_distances[cluster_id]

        # get next click candidate
        center_id, center_coo, center_gt, max_dist, candidates = get_next_click_coo_torch(
            coords_qv, error,
            labels_qv, pred_qv, pair_distances)

        if click_dict.get(str(int(center_gt))) == None:
            click_dict[str(int(center_gt))] = [int(center_id)]
            new_click_pos[str(int(center_gt))] = [center_coo]
            click_time_dict[str(int(center_gt))] = [click_order]
        else:
            click_dict[str(int(center_gt))].append(int(center_id))
            new_click_pos[str(int(center_gt))].append(center_coo)
            click_time_dict[str(int(center_gt))].append(click_order)

        click_order += 1
    
    click_num = len(error_cluster_ids)

    return click_dict, click_num, new_click_pos, click_time_dict


def get_next_simulated_click_multi_iter(current_num_iter, error_cluster_ids, error_cluster_ids_mask, pred_qv, labels_qv, coords_qv, error_distances):
    """Sample the next clicks for each error region
    """

    click_dict = {}
    new_click_pos = {}
    click_time_dict = {}
    click_iter_dict = {}
    click_order = 0

    random.shuffle(error_cluster_ids)

    for cluster_id in error_cluster_ids:

        error = error_cluster_ids_mask == cluster_id

        pair_distances = error_distances[cluster_id]

        # get next click candidate
        center_id, center_coo, center_gt, max_dist, candidates = get_next_click_coo_torch(
            coords_qv, error,
            labels_qv, pred_qv, pair_distances)

        if click_dict.get(str(int(center_gt))) == None:
            click_dict[str(int(center_gt))] = [int(center_id)]
            new_click_pos[str(int(center_gt))] = [center_coo]
            click_time_dict[str(int(center_gt))] = [click_order]
            click_iter_dict[str(int(center_gt))] = [int(1)]
        else:
            click_dict[str(int(center_gt))].append(int(center_id))
            new_click_pos[str(int(center_gt))].append(center_coo)
            click_time_dict[str(int(center_gt))].append(click_order)
            click_iter_dict[str(int(center_gt))].append(int(1))

        click_order += 1
    
    click_num = len(error_cluster_ids)

    return click_dict, click_num, new_click_pos, click_time_dict, click_iter_dict


def measure_error_size(discrete_coords, unique_labels):
    """Measure error size in 3D space
    """

    zero_indices = (unique_labels == 0)  # background
    one_indices = (unique_labels == 1)  # foreground
    if zero_indices.sum() == 0 or one_indices.sum() == 0:
        return None, None, None, -1, None, None

    # 输出内存使用信息用于调试
    num_zero = zero_indices.sum().item()
    num_one = one_indices.sum().item()
    estimated_memory_gb = (num_zero * num_one * 4) / (1024**3)  # 4 bytes per float32
    
    # print(f"[DEBUG] measure_error_size: Background points: {num_zero}, Foreground points: {num_one}")
    # print(f"[DEBUG] Estimated memory for cdist: {estimated_memory_gb:.2f} GB")
    
    # 如果估计内存超过阈值，直接跳过计算
    memory_threshold_gb = 13.0  # 可以根据GPU内存调整
    if estimated_memory_gb > memory_threshold_gb:
        print(f"[WARNING] Memory requirement too large ({estimated_memory_gb:.2f}GB > {memory_threshold_gb}GB), skipping...")
        print(f"[WARNING] This would cause CUDA OOM error!")
        return None  # 返回None表示跳过这个计算

    # All distances from foreground points to background points
    pairwise_distances = torch.cdist(discrete_coords[zero_indices, :], discrete_coords[one_indices, :])
    # Bg points on the border
    pairwise_distances, _ = torch.min(pairwise_distances, dim=0)

    return pairwise_distances

def get_simulated_clicks_o(pred_qv, labels_qv, coords_qv, current_num_clicks=None, training=True):
    """Sample simulated clicks. 
    The simulation samples next clicks from the top biggest error regions in the current iteration.
    """

    labels_qv = labels_qv.float()
    pred_label = pred_qv.float()

    error_mask = torch.abs(pred_label - labels_qv) > 0

    if error_mask.sum() == 0:
        return None, None, None, None

    cluster_ids = labels_qv * 96 + pred_label * 11

    error_region = coords_qv[error_mask]

    num_obj = (torch.unique(labels_qv) != 0).sum()
    

    error_clusters = cluster_ids[error_mask]
    error_cluster_ids = torch.unique(error_clusters)
    num_error_cluster = len(error_cluster_ids)

    error_cluster_ids_mask = torch.ones(coords_qv.shape[0], device=coords_qv.device) * -1
    error_cluster_ids_mask[error_mask] = error_clusters

    ### measure the size of each error cluster and store the distance
    error_sizes = {}
    error_distances = {}

    for cluster_id in error_cluster_ids:
        error = error_cluster_ids_mask == cluster_id
        pairwise_distances = measure_error_size(coords_qv, error)

        error_distances[int(cluster_id)] = pairwise_distances
        error_sizes[int(cluster_id)] = torch.max(pairwise_distances).tolist()

    error_cluster_ids_sorted = sorted(error_sizes, key=error_sizes.get, reverse=True)

    if training:
        if num_error_cluster >= num_obj:
            selected_error_cluster_ids = error_cluster_ids_sorted[:num_obj]
        else:
            selected_error_cluster_ids = error_cluster_ids_sorted
    else:    
        if current_num_clicks == 0:
            selected_error_cluster_ids = error_cluster_ids_sorted
        else:
            selected_error_cluster_ids = error_cluster_ids_sorted[:1]

    new_clicks, new_click_num, new_click_pos, new_click_time = get_next_simulated_click_multi(selected_error_cluster_ids, error_cluster_ids_mask, pred_qv, labels_qv, coords_qv, error_distances)
 
    return new_clicks, new_click_num, new_click_pos, new_click_time



def get_simulated_clicks(pred_qv, labels_qv, coords_qv, labels_shield_qv=None, current_num_clicks=None, training=True):
    """Sample simulated clicks. 
    The simulation samples next clicks from the top biggest error regions in the current iteration.
    """

    labels_qv = labels_qv.float()
    pred_label = pred_qv.float()

    error_mask = torch.abs(pred_label - labels_qv) > 0

    # 加上就是屏蔽区域，bg不允许在object内点击
    # if labels_shield_qv is not None:
    #     error_mask = error_mask & (labels_shield_qv == 1)

    # 调试，输出输入点云信息
    # total_points = coords_qv.shape[0]
    # error_points = error_mask.sum().item()
    # print(f"[DEBUG] get_simulated_clicks: Total points: {total_points}, Error points: {error_points}")
    # 调试，输出输入点云信息

    if error_mask.sum() == 0:
        # print("error_mask:",error_mask)
        # print("error_mask.sum() == 0")
        return None, None, None, None

    cluster_ids = labels_qv * 96 + pred_label * 11

    error_region = coords_qv[error_mask]

    num_obj = (torch.unique(labels_qv) != 0).sum()
    

    error_clusters = cluster_ids[error_mask]
    error_cluster_ids = torch.unique(error_clusters)
    num_error_cluster = len(error_cluster_ids)

    error_cluster_ids_mask = torch.ones(coords_qv.shape[0], device=coords_qv.device) * -1
    error_cluster_ids_mask[error_mask] = error_clusters

    ### measure the size of each error cluster and store the distance
    error_sizes = {}
    error_distances = {}

    for cluster_id in error_cluster_ids:
        error = error_cluster_ids_mask == cluster_id
        pairwise_distances = measure_error_size(coords_qv, error)

        error_distances[int(cluster_id)] = pairwise_distances
        error_sizes[int(cluster_id)] = torch.max(pairwise_distances).tolist()

    error_cluster_ids_sorted = sorted(error_sizes, key=error_sizes.get, reverse=True)

    if training:
        if num_error_cluster >= num_obj:
            selected_error_cluster_ids = error_cluster_ids_sorted[:num_obj]
        else:
            selected_error_cluster_ids = error_cluster_ids_sorted
    else:
        if current_num_clicks == 0:
            selected_error_cluster_ids = error_cluster_ids_sorted
        else:
            selected_error_cluster_ids = error_cluster_ids_sorted[:1]

    new_clicks, new_click_num, new_click_pos, new_click_time = get_next_simulated_click_multi(selected_error_cluster_ids, error_cluster_ids_mask, pred_qv, labels_qv, coords_qv, error_distances)
 
    return new_clicks, new_click_num, new_click_pos, new_click_time


def get_simulated_clicks_iter(pred_qv, labels_qv, coords_qv, labels_shield_qv=None, current_num_clicks=None, training=True):
    """Sample simulated clicks. 
    The simulation samples next clicks from the top biggest error regions in the current iteration.
    """

    labels_qv = labels_qv.float()
    pred_label = pred_qv.float()

    error_mask = torch.abs(pred_label - labels_qv) > 0

    # 加上就是屏蔽区域，bg不允许在object内点击
    # if labels_shield_qv is not None:
    #     error_mask = error_mask & (labels_shield_qv == 1)


    if error_mask.sum() == 0:
        return None, None, None, None, None

    cluster_ids = labels_qv * 96 + pred_label * 11

    error_region = coords_qv[error_mask]

    num_obj = (torch.unique(labels_qv) != 0).sum()
    

    error_clusters = cluster_ids[error_mask]
    error_cluster_ids = torch.unique(error_clusters)
    num_error_cluster = len(error_cluster_ids)

    error_cluster_ids_mask = torch.ones(coords_qv.shape[0], device=coords_qv.device) * -1
    error_cluster_ids_mask[error_mask] = error_clusters

    ### measure the size of each error cluster and store the distance
    error_sizes = {}
    error_distances = {}

    for cluster_id in error_cluster_ids:
        error = error_cluster_ids_mask == cluster_id
        pairwise_distances = measure_error_size(coords_qv, error)

        error_distances[int(cluster_id)] = pairwise_distances
        error_sizes[int(cluster_id)] = torch.max(pairwise_distances).tolist()

    error_cluster_ids_sorted = sorted(error_sizes, key=error_sizes.get, reverse=True)

    if training:
        if num_error_cluster >= num_obj:
            selected_error_cluster_ids = error_cluster_ids_sorted[:num_obj]
        else:
            selected_error_cluster_ids = error_cluster_ids_sorted
    else:
        if current_num_clicks == 0:
            selected_error_cluster_ids = error_cluster_ids_sorted
        else:
            selected_error_cluster_ids = error_cluster_ids_sorted[:1]
    
    current_num_iter = current_num_clicks

    new_clicks, new_click_num, new_click_pos, new_click_time, new_click_iter = get_next_simulated_click_multi_iter(current_num_iter, selected_error_cluster_ids, error_cluster_ids_mask, pred_qv, labels_qv, coords_qv, error_distances)
 
    return new_clicks, new_click_num, new_click_pos, new_click_time, new_click_iter


# 原版
# def extend_clicks(current_clicks, current_clicks_time, new_clicks, new_click_time):
#     """
#     Append new click to existing clicks
#     """

#     current_click_num = sum([len(c) for c in current_clicks_time.values()])

#     for obj_id, click_ids in new_clicks.items():
#         current_clicks[obj_id].extend(click_ids)
#         current_clicks_time[obj_id].extend([t+current_click_num for t in new_click_time[obj_id]])

#     return current_clicks, current_clicks_time

def count_clicks(click_time_dict):
    count = 0
    for v in click_time_dict.values():
        if isinstance(v, list):
            count += len(v)
        elif isinstance(v, dict):
            count += count_clicks(v)  # 递归
    return count

def extend_clicks_o(current_clicks, current_clicks_time, new_clicks, new_click_time):
    """Append new click to existing clicks
    """

    current_click_num = sum([len(c) for c in current_clicks_time.values()])

    for obj_id, click_ids in new_clicks.items():
        current_clicks[obj_id].extend(click_ids)
        current_clicks_time[obj_id].extend([t+current_click_num for t in new_click_time[obj_id]])

    return current_clicks, current_clicks_time



def extend_clicks(current_clicks, current_clicks_time, new_clicks, new_click_time):
    """
    Append new click to existing clicks
    """

    current_click_num = count_clicks(current_clicks_time)
    # print("current_clicks:",current_clicks)
    # print("current_clicks_time:",current_clicks_time)
    # print("new_clicks:",new_clicks)
    # print("new_click_time:",new_click_time)
    for encoded_part_id, click_ids in new_clicks.items():
        if encoded_part_id == '0':
            current_clicks[encoded_part_id].extend(click_ids)
            current_clicks_time[encoded_part_id].extend([t+current_click_num for t in new_click_time[encoded_part_id]])
        else:
            for object_id, part_dict in current_clicks.items():
                if object_id == '0':
                    continue
                if part_dict.get(encoded_part_id) is not None:
                    current_clicks[object_id][encoded_part_id].extend(click_ids)
                    current_clicks_time[object_id][encoded_part_id].extend([t+current_click_num for t in new_click_time[encoded_part_id]])
            # current_clicks[obj_id][str(part_id)].extend(click_ids)
            # current_clicks_time[obj_id][str(part_id)].extend([t+current_click_num for t in new_click_time[encoded_part_id]])

    return current_clicks, current_clicks_time


def extend_clicks_iter(current_clicks, current_clicks_time, current_clicks_iter, new_clicks, new_click_time, new_click_iter):
    """
    Append new click to existing clicks
    """

    current_click_num = count_clicks(current_clicks_time)

    for encoded_part_id, click_ids in new_clicks.items():
        if encoded_part_id == '0':
            current_clicks[encoded_part_id].extend(click_ids)
            current_clicks_time[encoded_part_id].extend([t+current_click_num for t in new_click_time[encoded_part_id]])

            if len(current_clicks_iter[encoded_part_id]) > 0:
                current_iter_num = max(current_clicks_iter[encoded_part_id])
            else:
                current_iter_num = 0  # 该part还没有点击过
            current_clicks_iter[encoded_part_id].extend([t+current_iter_num for t in new_click_iter[encoded_part_id]])

        else:
            for object_id, part_dict in current_clicks.items():
                if object_id == '0':
                    continue
                if part_dict.get(encoded_part_id) is not None:
                    current_clicks[object_id][encoded_part_id].extend(click_ids)
                    current_clicks_time[object_id][encoded_part_id].extend([t+current_click_num for t in new_click_time[encoded_part_id]])

                    if len(current_clicks_iter[object_id][encoded_part_id]) > 0:
                        current_iter_num = max(current_clicks_iter[object_id][encoded_part_id])
                    else:
                        current_iter_num = 0  # 该part还没有点击过
                    current_clicks_iter[object_id][encoded_part_id].extend([t+current_iter_num for t in new_click_iter[encoded_part_id]])

    return current_clicks, current_clicks_time, current_clicks_iter

