#!/usr/bin/env bash

CUDA_VISIBLE_DEVICES=1 python main.py --dataset_mode=multi_obj \
               --scan_folder=../../scans_final \
               --train_list=data/train_list_new.json \
               --val_list=data/val_list_new.json \
               --lr=1e-4 \
               --epochs=1100 \
               --lr_drop=1000 \
               --job_name=train_multi_obj_scannet40 \
               --resume=/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-08-12-22-56-27/checkpoint.pth