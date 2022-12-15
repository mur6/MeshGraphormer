import numpy as np
import torch

from src.modeling._mano import MANO
from manopth.manolayer import ManoLayer

# Mesh and SMPL utils

def main():
    mano_model = MANO().to("cpu")
    # mano_model.layer = mano_model.layer.cuda()

    for i in range(7 + 1):
        fill_value = i * 0.1
        print(f"fill_value={fill_value}")
        generate_and_save(fill_value=fill_value, filename=f"mesh_gra_zero_point_{i}")


"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT license.

Training and evaluation codes for 3D hand mesh reconstruction from an image
"""

from __future__ import absolute_import, division, print_function

import argparse
import itertools
import math
import os.path
from collections import namedtuple
from logging import DEBUG, INFO, basicConfig, critical, debug, error, exception, getLogger, info
from os.path import join
from pathlib import Path

import cv2
import imageio
import matplotlib.pyplot as plt
import numpy as np
import torch
import torchvision.models as models
import transforms3d
from pycocotools.coco import COCO
from torchvision.utils import make_grid
from tqdm import tqdm

import src.modeling.data.config as cfg
from my_model_tools import get_mano_model, get_model_for_train
from src.datasets.build import make_hand_data_loader
from src.datasets.hand_mesh_tsv import HandMeshTSVDataset, HandMeshTSVYamlDataset
from src.modeling.hrnet.config import config as hrnet_config


def build_hand_dataset(yaml_file, args, is_train=True, scale_factor=1):
    print(yaml_file)
    if not os.path.isfile(yaml_file):
        yaml_file = os.path.join(args.data_dir, yaml_file)
        # code.interact(local=locals())
        assert os.path.isfile(yaml_file)
    return HandMeshTSVYamlDataset(args, yaml_file, is_train, False, scale_factor)


MetaInfo = namedtuple("MetaInfo", "mano_pose,trans,betas,joints_2d,joints_3d")



def iter_meta_info(dataset_partial):
    for img_key, transfromed_img, meta_data in dataset_partial:
        pose = meta_data["pose"]
        # print(f"##############: pose={pose.shape}")
        # print(pose)
        mano_pose, trans = pose[:45], pose[45:]
        assert mano_pose.shape == (45,)
        # print(f"##############: mano_pose={mano_pose.shape}")
        # print(mano_pose)
        assert trans.shape == (3,)
        betas = meta_data["betas"]
        assert betas.shape == (10,)
        joints_2d = meta_data["joints_2d"][:, 0:2]
        assert joints_2d.shape == (21, 2)
        joints_3d = meta_data["joints_3d"][:, 0:3]
        assert joints_3d.shape == (21, 3)
        # print(mano_pose.shape, trans.shape, betas.shape, joints_2d.shape, joints_3d.shape)
        yield MetaInfo(mano_pose, trans, betas, joints_2d, joints_3d)




def main(args, *, train_yaml_file, num):
    dataset = build_hand_dataset(train_yaml_file, args, is_train=True)
    meta_info = list(iter_meta_info(itertools.islice(dataset, num)))
    print(meta_info)
    # keys = ("mano_pose", "trans", "betas", "joints_2d", "joints_3d")
    # print("[gphmer],mean,var")
    # for key in keys:
    #     m = sum(d[key].mean for d in dict_list) / num
    #     v = sum(d[key].var for d in dict_list) / num
    #     print(f"{key},{m:.03},{v:.03}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--multiscale_inference",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--train_yaml",
        type=Path,
        required=True,
        help="Yaml file with all data for training.",
    )
    parser.add_argument(
        "--num",
        type=int,
        default=1,
        # required=True,
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    main(args, train_yaml_file=args.train_yaml, num=args.num)
