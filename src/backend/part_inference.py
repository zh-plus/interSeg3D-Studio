# ------------------------------------------------------------------------
# Part Inference script for interactive segmentation
# ------------------------------------------------------------------------
import sys

sys.path.insert(0, './agile3d')

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
from argparse import Namespace

import MinkowskiEngine as ME
import numpy as np
import open3d as o3d
import torch

from app_utils import get_obj_color
from models import build_model
from partfield.config import default_argument_parser, setup
from lightning.pytorch import seed_everything, Trainer
from lightning.pytorch.strategies import DDPStrategy
from lightning.pytorch.callbacks import ModelCheckpoint
from plyfile import PlyData
from sklearn.cluster import AgglomerativeClustering, KMeans
import lightning
import torch
import glob
import os, sys
import numpy as np
import random
from logger import get_logger, StepTimer, timed

logger = get_logger("inference")


class PartInference:
    """Handles inference on a point cloud using a pre-trained model and user clicks."""

    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {self.device}")

        self.args = Namespace(
            config_file="partfield/cfg/final/demo.yaml",  # 配置文件路径
            opts=[
                "continue_ckpt", 'partfield/weights/model_objaverse.ckpt',
                "result_name", "partfield_features",
                "dataset.data_path", "temp",
                "is_pc", "True"
            ]
        )
        self.cfg = setup(self.args, freeze=False)

        # Initialize data structures
        self.point_cloud = None
        self.coords = None
        self.colors = None

        # parameters for cluster
        self.root = "exp_results/partfield_features"
        self.dump_dir = "exp_results/clustering"
        self.source_dir = "temp"
        self.use_agglo = False
        self.is_pc = True
        self.option = 1
        self.with_knn = False
        self.export_mesh = True

    def predict(self):
        seed_everything(self.cfg.seed)

        torch.manual_seed(0)
        random.seed(0)
        np.random.seed(0)

        checkpoint_callbacks = [ModelCheckpoint(
            monitor="train/current_epoch",
            dirpath=self.cfg.output_dir,
            filename="{epoch:02d}",
            save_top_k=100,
            save_last=True,
            every_n_epochs=self.cfg.save_every_epoch,
            mode="max",
            verbose=True
        )]
        
        # TODO: 这里按照原来的DDPS的分布式训练会产生端口冲突
        trainer = Trainer(devices=1,
                            accelerator="gpu",
                            precision="16-mixed",
                            strategy="auto",
                            max_epochs=self.cfg.training_epochs,
                            log_every_n_steps=1,
                            limit_train_batches=3500,
                            limit_val_batches=None,
                            callbacks=checkpoint_callbacks
                            )

        from partfield.model_trainer_pvcnn_only_demo import Model
        model = Model(self.cfg)        

        if self.cfg.remesh_demo:
            self.cfg.n_point_per_face = 10

        trainer.predict(model, ckpt_path=self.cfg.continue_ckpt)

    def load_ply_to_numpy(self,filename):
        """
        Load a PLY file and extract the point cloud as a (N, 3) NumPy array.

        Parameters:
            filename (str): Path to the PLY file.

        Returns:
            numpy.ndarray: Point cloud array of shape (N, 3).
        """
        # Read PLY file
        ply_data = PlyData.read(filename)
        
        # Extract vertex data
        vertex_data = ply_data["vertex"]
        
        # Convert to NumPy array (x, y, z)
        points = np.vstack([vertex_data["x"], vertex_data["y"], vertex_data["z"]]).T
        
        return points

    def solve_clustering(self,input_fname, uid, view_id, save_dir, out_render_fol, use_agglo=False, num_clusters=3, is_pc=False, option=1, with_knn=True, export_mesh=True):
        print(uid, view_id)
        if not is_pc:
            input_fname = f'{save_dir}/input_{uid}_{view_id}.ply'
            mesh = load_mesh_util(input_fname)

        else:
            pc = self.load_ply_to_numpy(input_fname) # 得到每个点的xyz数据

        ### Load inferred PartField features
        try:
            print(save_dir)
            point_feat = np.load(f'{save_dir}/part_feat_{uid}_{view_id}.npy')
        except:
            try:
                point_feat = np.load(f'{save_dir}/part_feat_{uid}_{view_id}_batch.npy')

            except:
                print()
                print("pointfeat loading error. skipping...")
                print(f'{save_dir}/part_feat_{uid}_{view_id}_batch.npy')
                return

        point_feat = point_feat / np.linalg.norm(point_feat, axis=-1, keepdims=True)

        if not use_agglo:
            clustering = KMeans(n_clusters=num_clusters, random_state=0).fit(point_feat)
            labels = clustering.labels_
            #重新编号成连续整数
            pred_labels = np.zeros((len(labels), 1))
            for i, label in enumerate(np.unique(labels)):
                # print(i, label)
                pred_labels[labels == label] = -(i+1)  # Assign RGB values to each label

            return pred_labels
                
            
        else:
            if is_pc:
                print("Not implemented error. Agglomerative clustering only for mesh inputs.")
                return null


    def cluster(self,index,catagory):
        ## 创建目录
        models = os.listdir(self.root)
        os.makedirs(self.dump_dir, exist_ok=True)

        cluster_fol = os.path.join(self.dump_dir, "cluster_out")
        os.makedirs(cluster_fol, exist_ok=True) 

        if self.export_mesh:
            ply_fol = os.path.join(self.dump_dir, "ply")
            os.makedirs(ply_fol, exist_ok=True)    

        #### Get existing model_ids ###
        all_files = os.listdir(os.path.join(self.dump_dir, "ply"))

        existing_model_ids = []
        for sample in all_files:
            uid = sample.split("_")[0]
            view_id = sample.split("_")[1]
            # sample_name = str(uid) + "_" + str(view_id)
            sample_name = str(uid)

            if sample_name not in existing_model_ids:
                existing_model_ids.append(sample_name)
        ##############################

        all_files = os.listdir(self.source_dir)
        selected = []
        for f in all_files:
            if ".ply" in f and self.is_pc and f.split(".")[0] not in existing_model_ids:
                selected.append(f)
            elif (".obj" in f or ".glb" in f) and not self.is_pc and f.split(".")[0] not in existing_model_ids:
                selected.append(f)
        
        print("Number of models to process: " + str(len(selected)))
        
        all_mask = {}
        for model in selected:
            fname = os.path.join(self.source_dir, model)
            uid = model.split(".")[-2]
            view_id = 0
            labelId = int(uid.split("_")[1])
            if labelId == index:
                return self.solve_clustering(fname, uid, view_id, save_dir=self.root, out_render_fol= self.dump_dir, use_agglo=self.use_agglo, num_clusters = catagory, is_pc=self.is_pc, option=self.option, with_knn=self.with_knn, export_mesh=self.export_mesh)
     

            
    def main():
        parser = default_argument_parser()
        args = parser.parse_args()
        cfg = setup(args, freeze=False)
        predict(cfg)

    if __name__ == '__main__':
        main()