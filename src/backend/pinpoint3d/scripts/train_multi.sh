#!/usr/bin/env bash

CUDA_VISIBLE_DEVICES=4 python main.py --dataset_mode=multi_obj \
               --scan_folder=/home/yehangjian/scans_final \
               --train_list=data/train_list_new.json \
               --val_list=data/val_list_new.json \
               --lr=1e-4 \
               --epochs=1100 \
               --lr_drop=1000 \
               --job_name=train_multi_obj_scannet40 \
               --resume=/ssd1/yhj/PartSeg/agile3d/checkpoint1099.pth \
               --only_parts_train=True
# /home/yehangjian/PartSeg/agile3d/weights/gt_only
# /home/yehangjian/Interactive-Partial-Segmentation/agile3d/checkpoint1099.pth
# /home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-01-00-30-29
# CUDA_VISIBLE_DEVICES=5 python main.py --dataset_mode=multi_obj \
#                --scan_folder=../../Scan_Multi \
#                --train_list=data/train_scan_multi.json \
#                --val_list=data/val_list_new.json \
#                --lr=1e-4 \
#                --epochs=1100 \
#                --lr_drop=1000 \
#                --job_name=train_multi_obj_scannet40 \
#                --resume=/home/yehangjian/Interactive-Partial-Segmentation/agile3d/checkpoint1099.pth \
#                --only_parts_train=True