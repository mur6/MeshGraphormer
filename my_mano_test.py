import argparse
import pickle
from pathlib import Path

import numpy as np
import torch
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from manopth.manolayer import ManoLayer


def generate_random_hand(batch_size=1, ncomps=6, mano_root="mano/models"):
    nfull_comps = ncomps + 3  # Add global orientation dims to PCA
    random_pcapose = torch.rand(batch_size, nfull_comps)
    mano_layer = ManoLayer(mano_root=mano_root)
    verts, joints = mano_layer(random_pcapose)
    return {"verts": verts, "joints": joints, "faces": mano_layer.th_faces}


def display_hand(hand_info, mano_faces=None, ax=None, alpha=0.2, batch_idx=0, save=True):
    """
    Displays hand batch_idx in batch of hand_info, hand_info as returned by
    generate_random_hand
    """
    if ax is None:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
    verts, joints = hand_info["verts"][batch_idx], hand_info["joints"][batch_idx]
    if mano_faces is None:
        ax.scatter(verts[:, 0], verts[:, 1], verts[:, 2], alpha=0.1)
    else:
        mesh = Poly3DCollection(verts[mano_faces], alpha=alpha)
        face_color = (141 / 255, 184 / 255, 226 / 255)
        edge_color = (50 / 255, 50 / 255, 50 / 255)
        mesh.set_edgecolor(edge_color)
        mesh.set_facecolor(face_color)
        ax.add_collection3d(mesh)
    ax.scatter(joints[:, 0], joints[:, 1], joints[:, 2], color="r")
    cam_equal_aspect_3d(ax, verts.numpy())
    if save:
        # plt.show()
        plt.savefig("aaa.png")


def cam_equal_aspect_3d(ax, verts, flip_x=False):
    """
    Centers view on cuboid containing hand and flips y and z axis
    and fixes azimuth
    """
    extents = np.stack([verts.min(0), verts.max(0)], axis=1)
    sz = extents[:, 1] - extents[:, 0]
    centers = np.mean(extents, axis=1)
    maxsize = max(abs(sz))
    r = maxsize / 2
    if flip_x:
        ax.set_xlim(centers[0] + r, centers[0] - r)
    else:
        ax.set_xlim(centers[0] - r, centers[0] + r)
    # Invert y and z axis
    ax.set_ylim(centers[1] + r, centers[1] - r)
    ax.set_zlim(centers[2] + r, centers[2] - r)


def make_hand(pca_pose, ncomps=45, mano_root="src/modeling/data"):
    # batch_size = 1
    # nfull_comps = ncomps + 3
    pca_pose = pca_pose.unsqueeze(0)
    mano_layer = ManoLayer(mano_root=mano_root)
    verts, joints = mano_layer(pca_pose)
    return {"verts": verts, "joints": joints, "faces": mano_layer.th_faces}


def main(base_path):
    meta_filepath = base_path / "datageneration/tmp/meta/00000000.pkl"
    b = meta_filepath.read_bytes()
    d = pickle.loads(b)
    a = d["mano_pose"]
    b = d["trans"]
    c = np.concatenate([a, b])
    print(a.shape, b.shape, c.shape)
    print(type(a))
    pca_pose = torch.from_numpy(c)
    hand_info = make_hand(pca_pose)
    verts = hand_info["verts"]
    joints = hand_info["joints"]
    assert verts.shape == (1, 778, 3)
    assert joints.shape == (1, 21, 3)
    display_hand(hand_info)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_path", type=Path, required=True)
    # parser.add_argument(
    #     "--pkl_filepath",
    #     type=Path,
    #     required=True,
    # )
    args = parser.parse_args()
    main(args.base_path)
