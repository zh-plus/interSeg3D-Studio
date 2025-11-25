#!/usr/bin/env bash
# python evaluate_part.py --dataset_mode=multi_obj \
#                --scan_folder=/home/yehangjian/Multiscan/scans \
#                --val_list=data/val_list_multi.json \
#                --output_dir=results/ScanNet_Part \
#                --checkpoint=/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-08-05-15-35-33/checkpoint0319.pth
# 2025-08-06-14-39-15  partagile_73_c
# 2025-08-02-17-49-06  tmux attach -t partagile_10
# checkpoints=(
#     2025-07-29-17-03-49/checkpoint1099.pth
#     # checkpoint0600.pth
# )

# voxel_sizes=(
#     # 0.001
#     # 0.005
#     # 0.01
#     # 0.04
#     0.05
# )

# for ckpt in "${checkpoints[@]}"; do
#     for vox in "${voxel_sizes[@]}"; do
#         echo "Running checkpoint=$ckpt voxel_size=$vox"
#         c
            
#     done
# done


# partagile_bg 600      2025-08-07-11-27-13
# partagile_10 600      2025-08-02-17-49-06
# partagile_73_c 600    2025-08-06-14-39-15
# partagile 600         2025-07-29-17-03-49
# partagile_73 600      2025-08-06-14-15-25
# partagile_iter 600    2025-08-02-19-00-35

#!/usr/bin/env bash
# 2025-08-14-09-54-02 原逻辑+新数据集
# 2025-08-14-16-40-43 双向跨层注意力 + 新数据集  0139
ckpt=/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-05-00-40-32/checkpoint0299.pth
name=$(basename "$ckpt" .pth)   # checkpoint1099
time_tag=$(basename $(dirname "$ckpt"))  # 2025-08-07-11-27-13
out_dir_ScanNet_new="results/ScanNet_new_${time_tag}_${name}"
out_dir_ScanNet_Multi="results/ScanNet_Multi_${time_tag}_${name}"


# python evaluate_part.py --dataset_mode=multi_obj \
# python /home/yehangjian/PartSeg/agile3d/evaluate_part.py --dataset_mode=multi_obj \

CUDA_VISIBLE_DEVICES=0 python evaluate_part.py --dataset_mode=multi_obj \
                --scan_folder=/home/yehangjian/Scan_Multi \
                --val_list=/home/yehangjian/PartSeg/agile3d/data/val_list_extend.json \
                --output_dir="$out_dir_ScanNet_new" \
                --checkpoint="$ckpt"
# val_list_extend_single, val_list_extend, val_list_extend_full, val_list_multi_single, val_list_multi_o ,val_list_multi_full
# CUDA_VISIBLE_DEVICES=7 python evaluate_part.py --dataset_mode=multi_obj \
#                 --scan_folder=/home/yehangjian/scans_final\
#                 --val_list=data/val_list_new.json \
#                 --output_dir="$out_dir_ScanNet_new" \
#                 --checkpoint="$ckpt"

# python evaluate_part.py --dataset_mode=multi_obj \
#                 --scan_folder=/home/yehangjian/Multiscan/origin_scans/new_scans\
#                 --val_list=data/val_list_multi_o.json \
#                 --output_dir="$out_dir_ScanNet_new" \
#                 --checkpoint="$ckpt"

