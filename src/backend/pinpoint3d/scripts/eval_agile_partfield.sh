#!/usr/bin/env bash

python eval_agile_partfield.py --dataset=scannet40 \
               --dataset_mode=multi_obj \
               --scan_folder=/home/yehangjian/scans_final\
               --val_list=data/val_list_extend_full.json \
               --output_dir=results/agile_partfield_extend \
               --checkpoint=/home/yehangjian/Interactive-Partial-Segmentation/agile3d/checkpoint1099_o.pth
               # --val_list_classes=data/ScanNet/single/object_classes.txt \
               # agile_partfield