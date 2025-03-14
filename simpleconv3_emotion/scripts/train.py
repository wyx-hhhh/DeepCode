'''
Author       : wyx-hhhh
Date         : 2023-04-29
LastEditTime : 2023-09-24
Description  : 
'''
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim import lr_scheduler
from torchvision import datasets, models, transforms
import os
from tensorboardX import SummaryWriter

from utils.get_config import Config
from models.model import simpleconv3

config = Config()

if device_type := config.get('device'):
    device = torch.device(device_type)
else:
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

writer = SummaryWriter('logs')


# 训练主函数
def train_model(model, criterion, optimizer, scheduler, epochs=25):
    for epoch in range(epochs):
        print('Epoch {}/{}'.format(epoch, epochs - 1))
        for phase in ['train', 'val']:
            if phase == 'train':
                optimizer.step()
                scheduler.step()
                model.train(True)  # 设置为训练模式
            else:
                model.train(False)  # 设置为验证模式

            running_loss = 0.0  #损失变量
            running_accs = 0.0  #精度变量
            number_batch = 0  #batch数量

            # 从dataloaders中获得数据
            for data in dataloaders[phase]:
                inputs, labels = data
                inputs = inputs.to(device)
                labels = labels.to(device)

                optimizer.zero_grad()  #清空梯度
                outputs = model(inputs)  #前向运行
                _, preds = torch.max(outputs.data, 1)  #使用max()函数对输出值进行操作，得到预测值索引
                loss = criterion(outputs, labels)  #计算损失
                if phase == 'train':
                    loss.backward()  #误差反向传播
                    optimizer.step()  #参数更新

                running_loss += loss.data.item()
                running_accs += torch.sum(preds == labels).item()
                number_batch += 1

            # 得到每一个epoch的平均损失与精度
            epoch_loss = running_loss / number_batch
            epoch_acc = running_accs / dataset_sizes[phase]

            # 收集精度和损失用于可视化
            if phase == 'train':
                writer.add_scalar('data/trainloss', epoch_loss, epoch)
                writer.add_scalar('data/trainacc', epoch_acc, epoch)
            else:
                writer.add_scalar('data/valloss', epoch_loss, epoch)
                writer.add_scalar('data/valacc', epoch_acc, epoch)

            print('{} Loss: {:.4f} Acc: {:.4f}'.format(phase, epoch_loss, epoch_acc))

    writer.close()
    return model


if __name__ == '__main__':
    image_size = 64  # 图像统一缩放大小
    crop_size = 48  # 图像裁剪大小，即训练输入大小
    nclass = 4  # 分类类别数
    model = simpleconv3(nclass)  #创建模型
    data_dir = './data'  #数据目录
    epochs = config.get('epochs')

    # 模型缓存接口
    if not os.path.exists('models'):
        os.mkdir('models')

    # 检查GPU是否可用，如果是使用GPU，否使用CPU
    model = model.to(device)

    # 创建数据预处理函数，训练预处理包括随机裁剪缩放、随机翻转、归一化，验证预处理包括中心裁剪，归一化
    data_transforms = {
        'train': transforms.Compose([
            transforms.RandomResizedCrop(48, scale=(0.8, 1.0), ratio=(0.8, 1.2)),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
        ]),
        'val': transforms.Compose([
            transforms.Resize(image_size),
            transforms.CenterCrop(crop_size),
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
        ]),
    }

    # 使用torchvision的dataset ImageFolder接口读取数据
    image_datasets = {x: datasets.ImageFolder(os.path.join(data_dir, x), data_transforms[x]) for x in ['train', 'val']}

    # 创建数据指针，设置batch大小，shuffle，多进程数量
    dataloaders = {x: torch.utils.data.DataLoader(image_datasets[x], batch_size=64, shuffle=True, num_workers=4) for x in ['train', 'val']}
    # 获得数据集大小
    dataset_sizes = {x: len(image_datasets[x]) for x in ['train', 'val']}

    # 优化目标使用交叉熵，优化方法使用带动量项的SGD，学习率迭代策略为step，每隔100个epoch，变为原来的0.1倍
    criterion = nn.CrossEntropyLoss()
    optimizer_ft = optim.SGD(model.parameters(), lr=0.1, momentum=0.9)
    step_lr_scheduler = lr_scheduler.StepLR(optimizer_ft, step_size=100, gamma=0.1)

    model = train_model(model=model, criterion=criterion, optimizer=optimizer_ft, scheduler=step_lr_scheduler, epochs=300)

    torch.save(model.state_dict(), 'checkpoints/model.pt')
