import torch.nn as nn
import torch.nn.functional as F


class Net(nn.Module):
    def __init__(self, output_classes):
        super(Net, self).__init__()

        linear_input_size = 256 * 91

        outputs = output_classes
        print("Dense Layers %s ... %s" % (linear_input_size, outputs))

        self.dropout = nn.Dropout(0.3)
        self.max_pool = nn.MaxPool2d(kernel_size=(1, 2), stride=2)

        self.conv1 = nn.Conv2d(1, 128, kernel_size=(5, 5), stride=1)
        self.bn1 = nn.BatchNorm2d(128)
        self.conv2 = nn.Conv2d(128, 128, kernel_size=(1, 5), stride=1)
        self.bn2 = nn.BatchNorm2d(128)

        self.conv3 = nn.Conv2d(128, 256, kernel_size=(1, 5), stride=1)
        self.bn3 = nn.BatchNorm2d(256)
        self.conv4 = nn.Conv2d(256, 256, kernel_size=(1, 5), stride=1)
        self.bn4 = nn.BatchNorm2d(256)

        self.fc1 = nn.Linear(linear_input_size, 256)
        self.fc2 = nn.Linear(256, outputs)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))

        x = self.max_pool(x)

        x = F.relu(self.bn3(self.conv3(x)))
        x = F.relu(self.bn4(self.conv4(x)))

        x = self.max_pool(x)
        x = self.dropout(x)

        x = F.relu(self.fc1(x.view(x.size(0), -1)))
        x = self.dropout(x)
        x = self.fc2(x)

        return F.log_softmax(x, dim=1)
