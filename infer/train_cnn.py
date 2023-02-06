from pathlib import Path
import argparse
import math

import torch
import torch.nn.functional as F
from torch.nn import Linear as Lin
from torch_cluster import fps, knn_graph
import torch_geometric.transforms as T

from torch.utils.data import TensorDataset, DataLoader
from timm.scheduler import CosineLRScheduler

from src.handinfo.data import load_data_for_geometric, get_mano_faces, load_data
from src.handinfo.losses import on_circle_loss, on_circle_loss_wrap
from src.model.pointnet import PointNetfeat, Simple_STN3d
from src.model.pointnet2 import PointNetCls


transform = T.Compose([
    # T.RandomJitter(0.01),
    T.RandomRotate(15, axis=0),
    T.RandomRotate(15, axis=1),
    T.RandomRotate(15, axis=2),
])
pre_transform = T.NormalizeScale()


def save_checkpoint(model, epoch, iteration=None):
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    checkpoint_dir = output_dir / f"checkpoint-{epoch}"
    checkpoint_dir.mkdir(exist_ok=True)
    model_to_save = model.module if hasattr(model, "module") else model

    torch.save(model_to_save, checkpoint_dir / "model.bin")
    torch.save(model_to_save.state_dict(), checkpoint_dir / "state_dict.bin")
    print(f"Save checkpoint to {checkpoint_dir}")
    return checkpoint_dir


def exec_train(train_loader, test_loader, *, model, train_datasize, test_datasize, device, epochs=1000):

    optimizer = optim.AdamW(model.parameters(), lr=0.005)
    E = nn.MSELoss()

    for epoch in range(epochs):
        losses = []
        current_loss = 0.0
        model.train()
        for i, (gt_vertices, gt_3d_joints, y, pca_mean, pca_components, normal_v, perimeter) in enumerate(train_loader):
            if device == "cuda":
                gt_vertices = gt_vertices.cuda()
                gt_3d_joints = gt_3d_joints.cuda()
                y = y.cuda()
                pca_mean = pca_mean.cuda()
                pca_components = pca_components.cuda()
                normal_v = normal_v.cuda()
                perimeter = perimeter.cuda()

            optimizer.zero_grad()
            y_pred = model(gt_3d_joints)
            loss = E(pca_mean.float().detach(), y_pred)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
            current_loss += loss.item() * y_pred.size(0)

        epoch_loss = current_loss / train_datasize
        print(f'Train Loss: {epoch_loss:.6f}')
        scheduler.step(epoch+1)
        model.eval()
        with torch.no_grad():
            current_loss = 0.0
            for gt_vertices, gt_3d_joints, y, pca_mean, pca_components, normal_v, perimeter in test_loader:
                if device == "cuda":
                    gt_vertices = gt_vertices.cuda()
                    gt_3d_joints = gt_3d_joints.cuda()
                    y = y.cuda()
                    pca_mean = pca_mean.cuda()
                    pca_components = pca_components.cuda()
                    normal_v = normal_v.cuda()
                    perimeter = perimeter.cuda()
                y_pred = model(gt_3d_joints)
                loss = E(pca_mean.float().detach(), y_pred)
                current_loss += loss.item() * y_pred.size(0)
            epoch_loss = current_loss / test_datasize
            print(f'Validation Loss: {epoch_loss:.6f}')
        if (epoch + 1) % 5 == 0:
            save_checkpoint(model, epoch+1)



def train(model, device, train_loader, train_datasize, optimizer):
    model.train()
    losses = []
    current_loss = 0.0

    for i, (gt_vertices, gt_3d_joints, vert_3d, pca_mean, pca_components, normal_v, perimeter) in enumerate(train_loader):
        if device == "cuda":
            gt_vertices = gt_vertices.cuda()
            gt_3d_joints = gt_3d_joints.cuda()
            gt_y = y.cuda()
            pca_mean = pca_mean.cuda()
            pca_components = pca_components.cuda()
            normal_v = normal_v.cuda()
            perimeter = perimeter.cuda()
            radius = perimeter / (2.0 * math.pi)
        # print(f"data.x: {data.x.shape}")
        # print(f"data.pos: {data.pos.shape}")
        optimizer.zero_grad()
        pred_output = model(gt_vertices)
        # print(f"data.y: {data.y.shape}")
        # print(f"output: {output.shape}")

        # batch_size = pred_output.shape[0]
        #print(f"verts: {verts.shape}")
        #print(f"faces: {faces.shape}")

        #.view(batch_size, 1538, 3)
        # print(f"bs_faces: {bs_faces.shape}")
        # gt_y = gt_y.view(batch_size, -1).float().contiguous()
        # loss = all_loss(output, gt_y, data, bs_faces)
        # loss = F.mse_loss(output, gt_y)
        # loss = cyclic_shift_loss(output, gt_y)
        # loss = on_circle_loss(output, data)
        loss = on_circle_loss(pred_output, vert_3d, gt_vertices, pca_mean, normal_v, radius)
        loss.backward()
        optimizer.step()
        losses.append(loss.item()) # 損失値の蓄積
        current_loss += loss.item() * pred_output.size(0)
    epoch_loss = current_loss / train_datasize
    print(f'Train Loss: {epoch_loss:.6f}')


def test(model, device, test_loader, test_datasize):
    model.eval()

    current_loss = 0.0
    # correct = 0
    for gt_vertices, gt_3d_joints, vert_3d, pca_mean, pca_components, normal_v, perimeter in test_loader:
        if device == "cuda":
            gt_vertices = gt_vertices.cuda()
            gt_3d_joints = gt_3d_joints.cuda()
            vert_3d = vert_3d.cuda()
            pca_mean = pca_mean.cuda()
            pca_components = pca_components.cuda()
            normal_v = normal_v.cuda()
            perimeter = perimeter.cuda()
            radius = perimeter / (2.0 * math.pi)
        with torch.no_grad():
            output = model(gt_vertices)
        loss = on_circle_loss(output, vert_3d, gt_vertices, pca_mean, normal_v, radius)
        current_loss += loss.item() * output.size(0)
    epoch_loss = current_loss / test_datasize
    print(f'Validation Loss: {epoch_loss:.6f}')


def main(resume_dir, input_filename, batch_size, args):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    train_dataset, test_dataset = load_data(input_filename)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, drop_last=True)
    train_datasize = len(train_dataset)
    test_datasize = len(test_dataset)
    print(f"train_datasize={train_datasize} test_datasize={test_datasize}")

    print(f"resume_dir: {resume_dir}")
    if resume_dir:
        if (resume_dir / "model.bin").exists() and \
            (resume_dir / "state_dict.bin").exists():
            if torch.cuda.is_available():
                model = torch.load(resume_dir / "model.bin")
                state_dict = torch.load(resume_dir / "state_dict.bin")
            else:
                model = torch.load(resume_dir / "model.bin", map_location=torch.device('cpu'))
                state_dict = torch.load(resume_dir / "state_dict.bin", map_location=torch.device('cpu'))
            model.load_state_dict(state_dict)
        else:
            raise Exception(f"{resume_dir} is not valid directory.")
    else:
        model = PointNetCls()
        if device == "cuda":
            model.to(device)

    print(f"model: {model.__class__.__name__}")
    model.eval()

    learning_rate = float(args.learning_rate)
    gamma = float(args.gamma)
    print(f"learning rate: {learning_rate}")
    print(f"gamma: {gamma}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer, gamma=gamma)

    # faces = get_mano_faces()
    # bs_faces = faces.repeat(batch_size, 1).view(batch_size, 1538, 3)

    for epoch in range(1, 1000 + 1):
        train(model, device, train_loader, train_datasize, optimizer)
        test(model, device, test_loader, test_datasize)
        if epoch % 5 == 0:
            save_checkpoint(model, epoch)
        scheduler.step(epoch)
        print(f"lr: {scheduler.get_last_lr()}")


def parse_args():
    from decimal import Decimal
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--learning_rate", type=Decimal, default=Decimal("0.01"))
    parser.add_argument("--gamma", type=Decimal, default=Decimal("0.85"))
    parser.add_argument(
        "--resume_dir",
        type=Path,
    )
    parser.add_argument(
        "--input_filename",
        type=Path,
        required=True,
    )
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_args()
    main(args.resume_dir, args.input_filename, args.batch_size, args)
