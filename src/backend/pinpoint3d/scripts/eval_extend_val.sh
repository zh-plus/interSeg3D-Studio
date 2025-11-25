#!/usr/bin/env bash
python evaluate_part.py --dataset_mode=multi_obj \
               --scan_folder=/home/yehangjian/scans_final\
               --val_list=data/val_list_extend.json \
               --output_dir=results/ScanNet_Part \
               --checkpoint=/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-08-07-11-27-13/checkpoint0119.pth