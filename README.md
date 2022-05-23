<h2 align='center'>torchssm</h2>
<h3 align='center'>Neural State-Space Models and Latent Dynamic Functions <br> for High-Dimensional Generative Time-series Modelling</h3>

<a name="about"/>

## About this Repository
This repository is meant to conceptually introduce and highlight implementation considerations for the recent class of models called <b>Neural State-Space Models (Neural SSMs)</b>. They leverage the classical state-space models with the flexibility of deep learning to approach high-dimensional generative time-series modelling and learning latent dynamics functions.

Included is an abstract PyTorch-Lightning training class structure with specific latent dynamic functions that inherit it, as well as common metrics used in their evaluation and training examples on common datasets. Further broken down via implementation is the distinction between <i>system identification</i> and <i>state estimation</i> approaches, which are reminiscent of their classic SSM counterparts and arise from fundamental differences in the underlying choice of probailistic graphical model (PGM).

![SavingFile](https://user-images.githubusercontent.com/32918812/169753112-bc849b24-fe13-4975-8697-fea95bb19fb5.png)
<p align='center'>Schematic of the two PGM forms of Neural SSMs</p>

<a name="toc"/>

## Table of Contents
- [About](#about)
- [Table of Contents](#toc)
- [What are Neural SSMs?](#neuralSSMwhat)
- [Choice of SSM PGM](#pgmChoice)
- [To-Do](#todo)
- [References](#references)

<a name="neuralSSMwhat"/>

## What are Neural SSMs?
An extension of classical state-space models, they at their core consist of a dynamic function of some latent states <b>z_k</b> and their emission to observations <b>x_k</b>, realized through the equations:
<p align='center'><img src="https://user-images.githubusercontent.com/32918812/169743189-057f52a5-8a08-4616-9516-3c60aca86b28.png" alt="centered image" /></p>
where <b>θ_z</b> represents the parameters of the latent dynamic function. The precise form of these functions can vary significantly - from deterministic or stochastic, linear or non-linear, and discrete or continuous.
<p> </p>
Due to their explicit differentiation of transition and emission and leveraging of structured equations, they have found success in learning interpretable latent dynamic spaces<sup>[1,2,3]</sup>, identifying physical systems from non-direct features<sup>[4,5,6]</sup> and uses in counterfactual forecasting<sup>[7,8,14]</sup>. 
<p> </p>
Given the fast pace of progress in latent dynamics modelling over recent years, many models have been presented under a variety of terminologies and proposed frameworks - examples being variational latent recurrent models<sup>[5,9,10,11,12]</sup>, deep state space models<sup>[1,2,3,7,13,14]</sup>, and deterministic encoding-decoding models<sup>[4,15,16]</sup>. Despite differences in appearance, they all adhere to the same conceptual framework of latent variable modelling and state-space disentanglement. As such, here we unify them under the term of Neural SSMs and segment them into the two base choices of probabilistic graphical models that they adhere to: <i>system identification</i> and <i>state estimation</i>. We highlight each PGM's properties and limitations with experimental evaluations on benchmark datasets.

<a name="pgmChoice"/>

## Choice of PGM - System Identification vs State Estimation
The PGM associated with each approach is determined by the latent variable chosen for inference.

<b>System states as latent variables</b>: The intuitive choice for the latent variable is the latent state <b>z_k</b> that underlies <b>x_k</b>, given that it is already latent in the system and is directly associated with the observations. The PGM of this form is shown under Fig. 1A

<a name="todo"/>

## To-Do
<h4>Repository-wise</h4>

- Make a ```state_estimation/``` folder in ```models/```
- Make a ```system_identification``` folder in ```models``` and shift current models to it

<h4>Model-wise</h4>

- Implement a version of DKF under ```state_estimation/```
- Implement a version of VRNN under ```state_estimation/```
- Implement a version of KVAE under ```system_identification``` (or any linear-gaussian ssm method)
- Implement a version of DVBF under ```system_identification```

<h4>Evaluation-wise</h4>

- Implement R^2 coefficient statistics from latent state to physical variables
- Implement latent walk visualizations against data-space observations (like in DVBF)


<a name="references"/>

## References
1. Maximilian Karl, Maximilian Soelch, Justin Bayer, and Patrick van der Smagt. Deep variational bayes filters: Unsupervised learning of state space models from raw data. In International Conference on Learning Representations, 2017.
2. Marco Fraccaro, Simon Kamronn, Ulrich Paquetz, and OleWinthery. A disentangled recognition and nonlinear dynamics model for unsupervised learning. In Advances in Neural Information Processing Systems, 2017.
3. Alexej Klushyn, Richard Kurle, Maximilian Soelch, Botond Cseke, and Patrick van der Smagt. Latent matters: Learning deep state-space models. Advances in Neural Information Processing Systems, 34, 2021.
4. Aleksandar Botev, Andrew Jaegle, Peter Wirnsberger, Daniel Hennes, and Irina Higgins. Which priors matter? benchmarking models for learning latent dynamics. In Advances in Neural Information Processing Systems, 2021.
5. C. Yildiz, M. Heinonen, and H. Lahdesmaki. ODE2VAE: Deep generative second order odes with bayesian neural networks. In Neural Information Processing Systems, 2020.
6. Batuhan Koyuncu. Analysis of ode2vae with examples. arXiv preprint arXiv:2108.04899, 2021.
7. Rahul G. Krishnan, Uri Shalit, and David Sontag. Structured inference networks for nonlinear state space models. In Association for the Advancement of Artificial Intelligence, 2017.
8. Daehoon Gwak, Gyuhyeon Sim, Michael Poli, Stefano Massaroli, Jaegul Choo, and Edward Choi. Neural ordinary differential equations for intervention modeling. arXiv preprint arXiv:2010.08304, 2020.
9. Junyoung Chung, Kyle Kastner, Laurent Dinh, Kratarth Goel, Aaron Courville, and Yoshua Bengio. A recurrent latent variable model for sequential data. In Advances in Neural Information Processing Systems, 2015.
10. Yulia Rubanova, Ricky T. Q. Chen, and David Duvenaud. Latent odes for irregularly-sampled time series. In Neural Information Processing Systems, 2019.
11. Tsuyoshi Ishizone, Tomoyuki Higuchi, and Kazuyuki Nakamura. Ensemble kalman variational objectives: Nonlinear latent trajectory inference with a hybrid of variational inference and ensemble kalman filter. arXiv preprint arXiv:2010.08729, 2020.
12. Justin Bayer, Maximilian Soelch, Atanas Mirchev, Baris Kayalibay, and Patrick van der Smagt. Mind the gap when conditioning amortised inference in sequential latent-variable models. arXiv preprint arXiv:2101.07046, 2021.
13. Ðor ̄de Miladinovi ́c, Muhammad Waleed Gondal, Bernhard Schölkopf, Joachim M Buhmann, and Stefan Bauer. Disentangled state space representations. arXiv preprint arXiv:1906.03255, 2019.
14. Zeshan Hussain, Rahul G. Krishnan, and David Sontag. Neural pharmacodynamic state space modeling, 2021.
15. Francesco Paolo Casale, Adrian Dalca, Luca Saglietti, Jennifer Listgarten, and Nicolo Fusi.Gaussian process prior variational autoencoders. Advances in neural information processing systems, 31, 2018.
16. Yingzhen Li and Stephan Mandt. Disentangled sequential autoencoder. arXiv preprint arXiv:1803.02991, 2018.
