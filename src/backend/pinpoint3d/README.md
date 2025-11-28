<p align="center">
<h1 align="center">PinPoint3D: Fine-Grained 3D Part Segmentation from a Few Clicks</h1>
<p align="center">
<a href="https://github.com/Quit123"><strong>Bojun Zhang</strong></a>
,
<a href="https://github.com/jian-77"><strong>Hangjian Ye</strong></a>
,
<a href="https://github.com/zh-plus"><strong>Hao Zheng</strong></a>
,
<a href="https://github.com/Cara-Zinc"><strong>Jianzheng Huang</strong></a>
<br>
<a href="https://pinpoint3d.online"><strong>Zhengyu Lin</strong></a>
, 
<a href="https://pinpoint3d.online"><strong>Zhenhong Guo</strong></a>
,
<a href="https://pinpoint3d.online"><strong>Feng Zheng</strong></a>
</p>
<!-- <h2 align="center">ICLR 2024</h2> -->
<h3 align="center"><a href="https://arxiv.org/abs/2509.25970">Paper</a> | <a href="https://pinpoint3d.online">Project Webpage</a></h3>
</p>
<p align="center">
<img src="./imgs/teaser.gif" width="500"/>
</p>
<p align="center">
<strong>PinPoint3D</strong> supports interactive multi-granularity 3D segmentation, where a user provides point clicks to obtain both object- and part-level masks efficiently in sparse scene point clouds.
</p>

## Installation 🔨

For training and evaluation, please follow the [installation.md](https://github.com/Quit123/PinPoint3D/blob/main/installation.md) to set up the environments.

## Interactive Tool 🎮

Please visit [interSeg3D-Studio
](https://github.com/zh-plus/interSeg3D-Studio) to experience the interactive annotation tool. It is a professional annotation platform designed specifically for the PinPoint3D model.

<p align="center">
<img src="./assets/demo.gif" width="75%" />
</p>

## Training 🚀

We design a new integrated dataset, PartScan, by integrating PartNet and ScanNet, and leveraging [PartField](https://github.com/nv-tlabs/PartField) to obtain part-level masks from object point clouds in ScanNet, thereby enhancing the generalization capability of PinPoint3D. You can download PartScan from [here](https://drive.google.com/file/d/1ahB1ugwTmGuNrvzHXqkEYerGs15DYSnH/view?usp=drive_link).

The command for training PinPoint3D with iterative training on PartScan is as follows:

```shell
bash ./scripts/train_partscan.sh
```


## Evaluation 📊

There are two datasets we provide for evaluation. Firstly, PartScan, a specialized dataset that integrates PartNet with ScanNet, and we evaluate the IoU of the original PartNet part masks within real-world ScanNet scenes. The second is MultiScan, which shows relatively modest results due to its coarser part granularity. You can download MultiScan from You can download MultiScan from [here](https://drive.google.com/file/d/1QlwEFGIjPmiXG-R-UZweMcqaEFisYu9t/view?usp=drive_link).

We provide the csv result files in the results folder, which can be directly fed into the evaluator for metric calculation. If you want to run the inference and do the evaluation yourself, download the pretrained [model](https://drive.google.com/file/d/1Rg2JDjh8iFGKwzP0UMLBCkce7bCvO5-D/view?usp=sharing) and move it to the weights folder. Then run:

### Evaluation on interactive multi parts 3D segmentation 

- PartNet in Scene:
```shell
bash ./scripts/eval_extend_val.sh
```

---

We provide two sets of quantitative benchmarks to evaluate PinPoint3D on both **fine-grained part-level segmentation** and **coarse object-level segmentation**.

The first table compares part-level segmentation performance across three models: the part-aware baseline **PointSAM**, the predecessor model **AGILE3D**, and our method **PinPoint3D**, evaluated under multi-click settings (IoU@1/3/5).

### Part-level Segmentation Results (SyntheticData & MultiScan)


|      Method      |            Eval             | IoU₁ | IoU₃ | IoU₅ |
|:----------------:|:---------------------------:|:----:|:----:|:----:|
|     PointSAM     | SyntheticData (random-part) | 46.2 | 50.1 | 51.4 |
|     AGile3D      | SyntheticData (random-part) | 39.8 | 58.4 | 64.9 |
| **PinPoint3D (Ours)** | SyntheticData (random-part) | **50.0** | **65.9** | **69.7** |
|     PointSAM     | SyntheticData (all-part)    | 48.4 | 52.6 | 52.7 |
|     AGile3D      | SyntheticData (all-part)    | 39.1 | 61.1 | 66.7 |
| **PinPoint3D (Ours)** | SyntheticData (all-part)    | **55.8** | **68.4** | **71.3** |
|     PointSAM     | MultiScan (random-part)     | **44.4** | 54.9 | 58.1 |
|     AGile3D      | MultiScan (random-part)     | 40.8 | 59.3 | 66.5 |
| **PinPoint3D (Ours)** | MultiScan (random-part)     | 44.0 | **60.8** | **66.8** |
|     PointSAM     | MultiScan (all-part)        | **44.9** | 54.0 | 56.1 |
|     AGile3D      | MultiScan (all-part)        | 42.1 | 61.2 | 67.5 |
| **PinPoint3D (Ours)** | MultiScan (all-part)        | 44.4 | **62.7** | **68.1** |

---

Beyond the primary part-segmentation task, we also test whether part-aware modeling impacts object-level segmentation, using PartScan-object and MultiScan (**with all parts merged into one object mask**). PinPoint3D maintains AGILE3D’s object-segmentation performance and even performs better on PartScan-object.

| Method                | Test Dataset | IoU₁  | IoU₃  | IoU₅  |
|-----------------------|--------------|-------|-------|-------|
| AGILE3D               | PartScan     | 83.64 | 96.87 | 97.69 |
| **PinPoint3D (Ours)** | PartScan     | **86.7** | **97.0** | **98.0** |
| **AGILE3D**               | MultiScan    | **58.46** | **75.04** | **81.02** |
| PinPoint3D (Ours) | MultiScan    | 57.1 | 72.3 | 78.6 |



## Citation 🎓

If you find our code or paper useful, please cite:

```shell

@misc{zhang2025pinpoint3dfinegrained3dsegmentation,
title={PinPoint3D: Fine-Grained 3D Part Segmentation from a Few Clicks}, 
author={Bojun Zhang and Hangjian Ye and Hao Zheng and Jianzheng Huang and Zhengyu Lin and Zhenhong Guo and Feng Zheng},
year={2025},
eprint={2509.25970},
archivePrefix={arXiv},
primaryClass={cs.CV},
url={https://arxiv.org/abs/2509.25970},
}

```








