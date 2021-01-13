from typing import Callable

import torch
import torch.nn.functional as F
from torch import nn

from pl_flash import ClassificationLightningTask


class TabularClassifier(ClassificationLightningTask):
    """LightningTask that classifies table rows.

    Args:
        num_columns: Number of columns in table (not including target column).
        num_classes: Number of classes to classify.
        embedding_sizes: List of (num_classes, emb_dim) to form categorical embeddings.
        hidden: Hidden dimension sizes.
        loss_fn: Loss function for training, defaults to cross entropy.
        optimizer: Optimizer to use for training, defaults to `torch.optim.Adam`.
        metrics: Metrics to compute for training and evaluation.
        learning_rate: Learning rate to use for training, defaults to `1e-3`
    """

    def __init__(
        self,
        num_columns,
        num_classes,
        embedding_sizes,
        hidden=[512],
        loss_fn: Callable = F.cross_entropy,
        optimizer=torch.optim.Adam,
        metrics=None,
        learning_rate: float = 1e-3,
    ):
        super().__init__(
            model=None,
            loss_fn=loss_fn,
            optimizer=optimizer,
            metrics=metrics,
            learning_rate=learning_rate,
        )

        num_num = num_columns - len(embedding_sizes)  # numerical columns
        input_size = num_num + sum(emb_dim for _, emb_dim in embedding_sizes)
        sizes = [input_size] + hidden + [num_classes]

        self.embs = nn.ModuleList([nn.Embedding(n_emb, emb_dim) for n_emb, emb_dim in embedding_sizes])
        self.bn_num = nn.BatchNorm1d(num_num) if num_num > 0 else None
        self.mlp = self._init_mlp(sizes)

    def _init_mlp(self, sizes):
        layers = []
        for i in range(len(sizes) - 2):
            layers.append(
                nn.Sequential(
                    nn.BatchNorm1d(sizes[i]),
                    nn.Linear(sizes[i], sizes[i + 1], bias=False),
                    nn.ReLU(),
                )
            )
        layers.append(nn.Linear(sizes[-2], sizes[-1]))
        return nn.Sequential(*layers)

    def forward(self, x_in):
        x_cat, x_num = x_in
        if len(self.embs):
            # concatenate embeddings for each categorical variable
            x = [e(x_cat[:, i]) for i, e in enumerate(self.embs)]
            x = torch.cat(x, dim=1)
        if self.bn_num is not None:
            x_num = self.bn_num(x_num)
            x = torch.cat([x_num, x], dim=1) if len(self.embs) else x_num
        x = self.mlp(x)
        return x