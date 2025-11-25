#!/usr/bin/env bash

python main.py --dataset_mode=multi_obj \
               --scan_folder=../../scans2 \
               --train_list=data/train_list.json \
               --val_list=data/val_list_focus_2.json \
               --lr=1e-4 \
               --epochs=1100 \
               --lr_drop=1000 \
               --job_name=traiqn_multi_obj_scannet40 \
               --resume=./output/2025-08-05-14-47-38/checkpoint0159.pth
