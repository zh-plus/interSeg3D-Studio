import subprocess
import argparse
import os
import glob

def find_latest_checkpoint(base_dir):
    """自动寻找最新的checkpoint"""
    folders = sorted(glob.glob(os.path.join(base_dir, "2025-*")), reverse=True)
    if not folders:
        return None
    checkpoints = sorted(glob.glob(os.path.join(folders[0], "checkpoint*.pth")), reverse=True)
    return checkpoints[0] if checkpoints else None

#    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-06-11-03-00/checkpoint0299.pth", # full click (300/550)    （待更新）
#    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-08-30-00-46-16/checkpoint0299.pth", # original click (300/600) （待更新）
#    "/home/yehangjian/PartSeg/agile3d/weights/gt_only/checkpoint0299.pth", # original click (300/600) (估计会改成human simulation click模式)
#    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-08-26-10-03-57/checkpoint0299.pth", #（2025-08-26-10-03-57:300/2025-08-30-00-52-19:600）(yhj跑) scannet+partfield
#    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-01-14-15-16/checkpoint0579.pth"(5%混合)
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=str, default="7", help="GPU id")
    parser.add_argument("--resume", type=str, default="", help="Path to checkpoint (if empty, auto find latest)")
    parser.add_argument("--val_list", type=str, default="data/val_list_new.json", help="Validation list JSON")
    args = parser.parse_args()
    log_file = "run_experiments_log.txt"
    N = 50
    # val_list_extend_single, val_list_extend, val_list_extend_full, val_list_multi_single, val_list_multi_o ,val_list_multi_full
    # /home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-06-11-03-00/checkpoint0399.pth

    resume_paths = [

                   # 真正的baseline
                #    "/home/yehangjian/PartSeg/agile3d/weights/agile2/checkpoint1099.pth", # 消融实验 agile2（1100）
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-08-21-30-39/checkpoint0919.pth", # 纯partnet (1100)
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-08-21-22-19/checkpoint0839.pth", # scannet+partfield（1100）
                #    "/home/yehangjian/PartSeg/agile3d/weights/multi/checkpoint1099.pth", # 消融实验 TAM strategy（1100）

                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-12-22-51-52/checkpoint0979.pth", # 消融实验 part transformer/2025-09-12-22-51-52（1100）
                   "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-08-21-22-04-55/checkpoint1099.pth", # 消融实验backbone（1100）



                # baseline
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-08-22-22-19/checkpoint0599.pth", # humansimulation (600)
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-01-14-15-16/checkpoint0599.pth", # 5-10 (600，原本训练集)
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-07-17-42-32/checkpoint0599.pth", # humansimulation400 (600，原本训练集)
                
                #    "/home/yehangjian/PartSeg/agile3d/weights/gt_only/checkpoint0599.pth", # gt_only (600)
                #    "/home/yehangjian/PartSeg/agile3d/weights/humansimu/checkpoint0599.pth", # humansimulation400 (600)
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-07-22-07-54/checkpoint0599.pth", # full (600，原本训练集)

                # click strategy
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-05-00-40-32/checkpoint0299.pth", # half click (300/580≈600) （保留）
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-11-15-36-41/checkpoint0599.pth", # full click (300)

                # 数据集：
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-08-21-30-39/checkpoint0299.pth", # 纯partnet (300)
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-08-21-22-19/checkpoint0299.pth", # scannet+partfield (300)

                # part transformer
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-06-10-46-05/checkpoint0299.pth", # 去掉part transformer（300/600）(保留)

                # backbone
                #    "/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output/2025-09-08-21-45-30/checkpoint0299.pth", # 解冻并训练backbone（300/600）

                # TAM（另一个服务器上跑的）

                # others
                #    "/home/yehangjian/PartSeg/agile3d/weights/humansimu/checkpoint0579.pth", # human simulation400 (600)
                #    "/home/yehangjian/PartSeg/agile3d/weights/gt_only/checkpoint0299.pth",(299/599/1099)
                   ]
    val_lists_Scan_Multi = [
                # "/home/yehangjian/PartSeg/agile3d/data/val_list_multi_single.json",
                # "/home/yehangjian/PartSeg/agile3d/data/val_list_multi_o.json",
                "/home/yehangjian/PartSeg/agile3d/data/val_list_multi_full.json"
                ]
    val_lists_scans_final = [
                # "/home/yehangjian/PartSeg/agile3d/data/val_list_extend_single.json",
                # "/home/yehangjian/PartSeg/agile3d/data/val_list_extend.json",
                "/home/yehangjian/PartSeg/agile3d/data/val_list_extend_full.json"
                ]
    # # 自动找最新 checkpoint
    # resume_path = args.resume
    # if not resume_path:
    #     resume_path = find_latest_checkpoint("/home/yehangjian/Interactive-Partial-Segmentation/agile3d/output")
    #     if not resume_path:
    #         raise FileNotFoundError("No checkpoint found!")
    
    log_dir = "logs_eval"
    os.makedirs(log_dir, exist_ok=True)  # 确保日志目录存在

    for resume_path in resume_paths:
        for val_list in val_lists_scans_final:
            cmd = [
                "python", "../evaluate_part.py",
                "--dataset_mode=multi_obj",
                "--scan_folder=/home/yehangjian/scans_final",
                f"--val_list={val_list}",
                f"--checkpoint={resume_path}",
            ]
            env = {"CUDA_VISIBLE_DEVICES": args.gpu, **os.environ}

            resume_tag = os.path.basename(os.path.dirname(resume_path))
            val_tag = os.path.splitext(os.path.basename(val_list))[0]
            log_file = os.path.join(log_dir, f"log_{resume_tag}_{val_tag}.txt")
            print(f"Running with GPU {args.gpu}, resume={resume_tag}, val={val_tag}")
            # 捕获输出
            result = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            # 只保留最后 N 行
            lines = result.stdout.strip().splitlines()
            tail = "\n".join(lines[-N:])
            with open(log_file, "w") as f:
                f.write(tail)
    
    for resume_path in resume_paths:
        for val_list in val_lists_Scan_Multi:
            cmd = [
                "python", "../evaluate_part.py",
                "--dataset_mode=multi_obj",
                "--scan_folder=/home/yehangjian/Multiscan/origin_scans/new_scans",
                f"--val_list={val_list}",
                f"--checkpoint={resume_path}",
            ]
            env = {"CUDA_VISIBLE_DEVICES": args.gpu, **os.environ}

            resume_tag = os.path.basename(os.path.dirname(resume_path))
            val_tag = os.path.splitext(os.path.basename(val_list))[0]
            log_file = os.path.join(log_dir, f"log_{resume_tag}_{val_tag}.txt")
            print(f"Running with GPU {args.gpu}, resume={resume_tag}, val={val_tag}")
            # 捕获输出
            result = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            # 只保留最后 N 行
            lines = result.stdout.strip().splitlines()
            tail = "\n".join(lines[-N:])
            with open(log_file, "w") as f:
                f.write(tail)

if __name__ == "__main__":
    main()
