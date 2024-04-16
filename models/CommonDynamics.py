"""
@file CommonDynamics.py

A common class that each latent dynamics function inherits.
Holds the training + validation step logic and the VAE components for reconstructions.
"""
import os
import json
import torch
import numpy as np
import torch.nn as nn
import pytorch_lightning
import utils.metrics as metrics
import matplotlib.pyplot as plt

from sklearn.manifold import TSNE
from models.CommonVAE import LatentStateEncoder, EmissionDecoder
from utils.plotting import show_images, get_embedding_trajectories
from utils.utils import determine_annealing_factor, CosineAnnealingWarmRestartsWithDecayAndLinearWarmup


class LatentDynamicsModel(pytorch_lightning.LightningModule):
    def __init__(self, cfg):
        """
        Generic implementation of a Latent Dynamics Model
        Holds the training and testing boilerplate, as well as experiment tracking
        :param cfg: passed in hydra configdict
        """
        super().__init__()
        # Config
        self.cfg = cfg
        self.setting = 'train'

        # Encoder + Decoder
        self.encoder = LatentStateEncoder(cfg)
        self.decoder = EmissionDecoder(cfg)

        # Recurrent dynamics function
        self.dynamics_func = None
        self.dynamics_out = None

        # Number of steps for training
        self.n_updates = 0

        # Loss function
        self.reconstruction_loss = nn.MSELoss(reduction='none')

        self.outputs = list()
        self.validation_step_outputs = list()

    def forward(self, x, generation_len):
        """ Placeholder function for the dynamics forward pass """
        raise NotImplementedError("In forward function: Latent Dynamics function not specified.")

    def model_specific_loss(self, x, x_rec, train=True):
        """ Placeholder function for any additional loss terms a dynamics function may have """
        return 0.0

    def model_specific_plotting(self, version_path, outputs):
        """ Placeholder function for any additional plots a dynamics function may have """
        return None

    def configure_optimizers(self):
        """
        Most standard NSSM models have a joint optimization step under one ELBO, however there is room
        for EM-optimization procedures based on the PGM.

        By default, we assume a joint optim with the Adam Optimizer. We additionally include LR Warmup and
        CosineAnnealing with decay for standard learning rate care during training.

        For CosineAnnealing, we set the LR bounds to be [LR * 1e-2, LR]
        """
        optim = torch.optim.AdamW(self.parameters(), lr=self.cfg.training.learning_rate, weight_decay=1.0)

        # Build the scheduler if using it
        if self.cfg.training.scheduler.use is True:
            scheduler = CosineAnnealingWarmRestartsWithDecayAndLinearWarmup(
                optim,
                T_0=self.cfg.training.scheduler.restart_interval, T_mult=1,
                eta_min=self.cfg.training.learning_rate * 1e-2,
                warmup_steps=self.cfg.training.scheduler.warmup_steps,
                decay=self.cfg.training.scheduler.decay
            )

            # Explicit dictionary to state how often to ping the scheduler
            scheduler = {
                'scheduler': scheduler,
                'frequency': 1,
                'interval': 'step'
            }

            return [optim], [scheduler]

        # Otherwise just return the optimizer
        return optim

    def on_train_start(self):
        """
        Before a training session starts, we set some model variables and save a JSON configuration of the
        used hyperparameters to allow for easy load-in at test-time.
        """
        # Get total number of parameters for the model and save
        self.log("total_num_parameters", float(sum(p.numel() for p in self.parameters() if p.requires_grad)), prog_bar=False)

        # Make image dir in lightning experiment folder if it doesn't exist
        if not os.path.exists(f"{self.logger.log_dir}/images/"):
            os.mkdir(f"{self.logger.log_dir}/images/")

    def get_step_outputs(self, batch, generation_len):
        """
        Handles the process of pre-processing and subsequence sampling a batch,
        as well as getting the outputs from the models regardless of step
        :param batch: list of dictionary objects representing a single image
        :param generation_len: how far out to generate for, dependent on the step (train/val)
        :return: processed model outputs
        """
        # Deconstruct batch
        _, images, states, controls, labels = batch

        # Same random portion of the sequence over generation_len, saving room for backwards solving
        random_start = np.random.randint(generation_len, images.shape[1] - self.cfg.training.z_amort - generation_len)

        # Get forward sequences
        images = images[:, random_start:random_start + generation_len + self.cfg.training.z_amort]
        states = states[:, random_start:random_start + generation_len + self.cfg.training.z_amort]

        # Get predictions
        preds, embeddings = self(images, generation_len)

        # Restrict images to start from after inference, for metrics and likelihood
        images = images[:, self.cfg.training.z_amort:]
        states = states[:, self.cfg.training.z_amort:]
        return images, states, labels, preds, embeddings

    def get_step_losses(self, images, preds):
        """
        Handles getting the ELBO terms for the given step
        :param images: ground truth images
        :param images_rev: grouth truth images, reversed for some models' secondary TRS loss
        :param preds: forward predictions from the model
        :return: likelihood, kl on z0, model-specific dynamics loss
        """
        # Reconstruction loss for the sequence and z0
        likelihood = self.reconstruction_loss(preds, images)
        likelihood = likelihood.reshape([likelihood.shape[0] * likelihood.shape[1], -1]).sum([-1]).mean()

        # Initial encoder loss, KL[q(z_K|x_0:K) || p(z_K)]
        klz = self.encoder.kl_z_term()

        # Get the loss terms from the specific latent dynamics loss
        dynamics_loss = self.model_specific_loss(images, preds)
        return likelihood, klz, dynamics_loss

    def get_epoch_metrics(self, outputs, setting='train'):
        """
        Takes the dictionary of saved batch metrics, stacks them, and gets outputs to log in the Tensorboard.
        :param outputs: list of dictionaries with outputs from each back
        :return: dictionary of metrics aggregated over the epoch
        """
        # Convert outputs to Tensors and then Numpy arrays
        images = torch.vstack([out["images"] for out in outputs]).cpu().numpy()
        preds = torch.vstack([out["preds"] for out in outputs]).cpu().numpy()

        # Iterate through each metric function and add to a dictionary
        out_metrics = {}
        for met in self.cfg.training.metrics:
            metric_function = getattr(metrics, met)
            out_metrics[met] = metric_function(images, preds, cfg=self.cfg, setting=setting)[0]

        # Return a dictionary of metrics
        return out_metrics

    def training_step(self, batch, batch_idx):
        """
        PyTorch-Lightning training step where the network is propagated and returns a single loss value,
        which is automatically handled for the backward update
        :param batch: list of dictionary objects representing a single image
        :param batch_idx: how far in the epoch this batch is
        """
        # Get the generation length - either fixed or random between [1,T] depending on flags
        generation_len = np.random.randint(1, self.cfg.training.gen_len['train']) \
            if self.cfg.training.gen_len['varying'] is True else self.cfg.training.gen_len['train']

        # Get model outputs from batch
        images, states, labels, preds, embeddings = self.get_step_outputs(batch, generation_len)

        # Get model loss terms for the step
        likelihood, klz, dynamics_loss = self.get_step_losses(images, preds)

        # Determine KL annealing factor for the current step
        kl_factor = determine_annealing_factor(self.n_updates, anneal_update=1000)

        # Build the full loss
        loss = likelihood + kl_factor * ((self.cfg.training.betas.z0 * klz) + (self.cfg.training.betas.kl * dynamics_loss))

        # Log ELBO loss terms
        self.log_dict({
            "likelihood": likelihood,
            "kl_z": self.cfg.training.betas.z0 * klz,
            "dynamics_loss": self.cfg.training.betas.kl * dynamics_loss,
            "kl_factor": kl_factor
        })

        # Return outputs as dict
        self.n_updates += 1
        out = {"loss": loss, "labels": labels.detach(), "preds": preds.detach(), "images": images.detach()}
        self.outputs.append(out)
        return out

    def on_train_batch_end(self, outputs, batch, batch_idx):
        """ Given the iterative training, check on every batch's end whether it is evaluation time or not """
        if batch_idx % self.cfg.training.log_interval == 0 and batch_idx != 0:
            # Log epoch metrics on saved batches
            metrics = self.get_epoch_metrics(self.outputs[:self.cfg.dataset.batches_to_save], setting='train')
            for metric in metrics.keys():
                self.log(f"train_{metric}", metrics[metric], prog_bar=True)

            # Every 10 windows of updates, get images from train
            if batch_idx % (self.cfg.training.log_interval * 10) == 0 and batch_idx != 0:
                # Show side-by-side reconstructions
                show_images(self.outputs[0]["images"], self.outputs[0]["preds"],
                            f'{self.logger.log_dir}/images/recon{batch_idx}train.png', num_out=5)

                # Get per-dynamics plots
                self.model_specific_plotting(self.logger.log_dir, self.outputs)

            # Clear out the old cache
            self.outputs = list()

    def validation_step(self, batch, batch_idx):
        """
        PyTorch-Lightning validation step. Similar to the training step but on the given val set under torch.no_grad()
        :param batch: list of dictionary objects representing a single image
        :param batch_idx: how far in the epoch this batch is
        """
        # Get model outputs from batch
        images, states, labels, preds, embeddings = self.get_step_outputs(batch, self.cfg.training.gen_len['val'])

        # Get model loss terms for the step
        likelihood, klz, dynamics_loss = self.get_step_losses(images, preds)

        # Build the full loss
        loss = likelihood + dynamics_loss

        # Log validation likelihood and metrics
        self.log("val_likelihood", likelihood, prog_bar=True)

        # Return outputs as dict
        out = {"loss": loss}
        if batch_idx < self.cfg.dataset.batches_to_save:
            out["preds"] = preds.detach()
            out["images"] = images.detach()
        self.validation_step_outputs.append(out)
        return out

    def on_validation_epoch_end(self):
        """
        Every N epochs, get a validation reconstruction sample
        """
        # Log epoch metrics on saved batches
        metrics = self.get_epoch_metrics(self.validation_step_outputs[:self.cfg.dataset.batches_to_save], setting='val')
        for metric in metrics.keys():
            self.log(f"val_{metric}", metrics[metric], prog_bar=True)

        # Get image reconstructions
        show_images(self.validation_step_outputs[0]["images"], self.validation_step_outputs[0]["preds"],
                    f'{self.logger.log_dir}/images/recon{self.n_updates}val.png', num_out=5)

    def test_step(self, batch, batch_idx):
        """
        PyTorch-Lightning testing step.
        :param batch: list of dictionary objects representing a single image
        :param batch_idx: how far in the epoch this batch is
        """
        # Get model outputs from batch
        images, states, labels, preds, embeddings = self.get_step_outputs(batch, self.cfg.training.gen_len['test'])

        # Build output dictionary
        out = {"states": states.detach().cpu(), "embeddings": embeddings.detach().cpu(),
               "preds": preds.detach().cpu(), "images": images.detach().cpu(), "labels": labels.detach().cpu()}
        return out

    def test_epoch_end(self, batch_outputs):
        """
        For testing end, save the predictions, gt, and MSE to NPY files in the respective experiment folder
        :param outputs: list of outputs from the validation steps at batch 0
        """
        # Stack all output types and convert to numpy
        outputs = dict()
        for key in batch_outputs[0].keys():
            stack_method = torch.concatenate if key == "som_assignments" else torch.vstack
            outputs[key] = stack_method([output[key] for output in batch_outputs]).numpy()

        # Iterate through each metric function and add to a dictionary
        out_metrics = {}
        for met in self.cfg.training.metrics:
            metric_function = getattr(metrics, met)
            metric_mean, metric_std = metric_function(outputs["images"], outputs["preds"], cfg=self.cfg, setting='test')
            out_metrics[f"{met}_mean"], out_metrics[f"{met}_std"] = float(metric_mean), float(metric_std)
            print(f"=> {met}: {metric_mean:4.5f}+-{metric_std:4.5f}")

        # Set up output path and create dir
        output_path = f"{self.logger.log_dir}/test_{self.setting}"
        if not os.path.exists(output_path):
            os.mkdir(output_path)

        # Save files
        if self.cfg.save_files is True:
            np.save(f"{output_path}/test_{self.setting}_recons.npy", outputs["preds"])
            np.save(f"{output_path}/test_{self.setting}_images.npy", outputs["images"])
            np.save(f"{output_path}/test_{self.setting}_labels.npy", outputs["labels"])

        # Save some examples
        show_images(outputs["images"][:10], outputs["preds"][:10], f"{output_path}/test_{self.setting}_examples.png", num_out=5)

        # Save trajectory examples
        get_embedding_trajectories(outputs["embeddings"][0], outputs["states"][0], f"{output_path}/")

        # Get Z0 TSNE
        tsne = TSNE(n_components=2, perplexity=30, learning_rate=200, n_iter=1000, early_exaggeration=12)
        fitted = tsne.fit(outputs["embeddings"][:, 0])
        tsne_embedding = fitted.embedding_

        for i in np.unique(outputs["labels"]):
            subset = tsne_embedding[np.where(outputs["labels"] == i)[0], :]
            plt.scatter(subset[:, 0], subset[:, 1], c=next(plt.gca()._get_lines.prop_cycler)['color'])

        plt.title("t-SNE Plot of Z0 Embeddings")
        plt.legend(np.unique(outputs["labels"]), loc='center left', bbox_to_anchor=(1, 0.5))
        plt.savefig(f"{output_path}/test_{self.setting}_Z0tsne.png", bbox_inches='tight')
        plt.close()

        # Save metrics to JSON in checkpoint folder
        with open(f"{output_path}/test_{self.setting}_metrics.json", 'w') as f:
            json.dump(out_metrics, f)

        # Save metrics to an easy excel conversion style
        with open(f"{output_path}/test_{self.setting}_excel.txt", 'w') as f:
            for metric in self.cfg.training.metrics:
                f.write(f"{out_metrics[f'{metric}_mean']:0.3f}({out_metrics[f'{metric}_std']:0.3f}),")
