# REFERENCES

Bibliography for `METHODS_REVIEW.md`. The sources were read in this session (2026-09-26) by six research passes, and their
per-area notes are in `notes/`.

**Read level.**

- **full**: method section or full text read (HTML, text-extracted PDF, or a full-text summary);
- **abstract**: the abstract page, or an abstract-level summary of it;
- **metadata**: bibliographic record or search-result summary only;
- **background**: standard reference not read in this session.

`[unverified]` marks bibliographic details (venue, pages, author list, licence) that could not be confirmed. Each source is
listed once, under the area where it is used most.

## Area 1: Interventional state-space models

1. Nejatbakhsh, A., Wang, Y. (2025). Identifying Neural Dynamics Using Interventional State Space Models. *ICML 2025*, PMLR 267:45877-45894. https://proceedings.mlr.press/v267/nejatbakhsh25a.html ; code https://github.com/amin-nejat/issm (no licence file). **full** (text-extracted PDF + code summaries; the exact wording of the pair condition is [unverified]).
2. Wagenmaker, A., Mi, L., Rozsa, M., Bull, M. S., Svoboda, K., Daie, K., Golub, M. D., Jamieson, K. (2024). Active learning of neural population dynamics using two-photon holographic optogenetics. *NeurIPS 2024*. arXiv:2412.02529. **full** (arXiv HTML v1; methods content only).
3. [Authors not captured]. (2025). Towards Identifiability of Interventional Stochastic Differential Equations. arXiv:2505.15987. **full** (HTML) [authors/venue unverified].
4. von Kügelgen, J., Ketterer, J., Vollenweider, M., Scholkemper, M., Shen, X., Meinshausen, N., Peters, J. (2025/2026). Extrapolation Guarantees for Perturbation Modeling Under the Additive Latent Shift Assumption. arXiv:2504.18522 (v3). **full** (HTML).
5. Vahidi, P., Sani, O. G., Shanechi, M. M. (2025). BRAID: Input-Driven Nonlinear Dynamical Modeling of Neural-Behavioral Data. *ICLR 2025*. arXiv:2509.18627 ; code https://github.com/ShanechiLab/BRAID. **full** (HTML).
6. Schimel, M., Kao, T.-C., Jensen, K. T., Hennequin, G. (2022). iLQR-VAE: control-based learning of input-driven dynamics with applications to neural data. *ICLR 2022*. bioRxiv 10.1101/2021.10.07.463540. **full** (bioRxiv).
7. Sussillo, D., Jozefowicz, R., Abbott, L. F., Pandarinath, C. (2016). LFADS - Latent Factor Analysis via Dynamical Systems. arXiv:1608.06315. **abstract**.
8. Pandarinath, C., et al. (2018). Inferring single-trial neural population dynamics using sequential auto-encoders. *Nature Methods* 15:805-815. doi:10.1038/s41592-018-0109-9. **background** [pages unverified].
9. Versteeg, C., et al. (2025). Computation-through-Dynamics Benchmark: Simulated datasets and quality metrics. bioRxiv 10.1101/2025.02.07.637062 ; code https://github.com/neurallatents/computation-through-dynamics. **full** (full-text summary).
10. Yang, Y., Connolly, A. T., Shanechi, M. M. (2018). A control-theoretic system identification framework and a real-time closed-loop clinical simulation testbed for electrical brain stimulation. *J. Neural Engineering* 15(6):066007. doi:10.1088/1741-2552/aad1a8. **abstract**.
11. Baumgartner, Lei, Watson, Posner (2026). Disentangling Dynamical Systems: Causal Representation Learning Meets Local Sparse Attention. arXiv:2603.14483. **full** (method summary) [first names unverified].
12. Liu, Y., Chen, Y. (2026). Low-Rank Dynamics-Effective Latent Carriers for Counterfactual Rollout in Learned World Models. arXiv:2608.15156. **abstract**.
13. Salehkaleybar, S. (2026). One Intervention per Component is Enough: Towards Identifiability in Linear Stochastic Dynamics from Steady State. arXiv:2609.19955. **abstract**.
14. Peters, J., Bauer, S., Pfister, N. (2020). Causal models for dynamical systems. arXiv:2001.06208. **abstract**.
15. Linderman, S. W., Miller, A. C., Adams, R. P., Blei, D. M., Paninski, L., Johnson, M. J. (2017). Recurrent switching linear dynamical systems. *AISTATS 2017*. arXiv:1610.08466. **abstract**.
16. Toloubidokhti, M., et al. (2022). Neural State-Space Modeling with Latent Causal-Effect Disentanglement. MLMI workshop. arXiv:2209.12387. **abstract**.
17. [Review] (2026). Machine Learning Methods for Studying Latent Neural Activity Dynamics. arXiv:2606.10530. **full** (perturbation section only) [authors not recorded].
18. Tan, et al. (2026). What can latent world models know? Physical parameter identifiability. arXiv:2607.27017. **abstract** [authors unverified].
19. dynamax (probml): JAX state-space model library. https://github.com/probml/dynamax. MIT. **docs**.
20. ssm (Linderman lab): https://github.com/lindermanlab/ssm. MIT. **docs**.

## Area 2: Causal representation learning and causal abstraction

21. Squires, C., Seigal, A., Bhate, S., Uhler, C. (2023). Linear Causal Disentanglement via Interventions. *ICML 2023*. arXiv:2211.16467. **abstract** (+ theorem summary).
22. Varici, B., Acarturk, E., Shanmugam, K., Kumar, A., Tajer, A. (2025). Score-based Causal Representation Learning: Linear and General Transformations. *JMLR* 26(112):1-90. arXiv:2402.00849 ; code https://github.com/acarturk-e/score-based-crl. **abstract**.
23. Varici, B., Acarturk, E., Shanmugam, K., Tajer, A. (2024). General Identifiability and Achievability for Causal Representation Learning. *AISTATS 2024*. arXiv:2310.15450. **metadata**.
24. Varici, B., Acarturk, E., Shanmugam, K., Tajer, A. (2024). Linear Causal Representation Learning from Unknown Multi-node Interventions. *NeurIPS 2024*. arXiv:2406.05937. **abstract**.
25. Buchholz, S., Rajendran, G., Rosenfeld, E., Aragam, B., Schölkopf, B., Ravikumar, P. (2023). Learning Linear Causal Representations from Interventions under General Nonlinear Mixing. *NeurIPS 2023*. arXiv:2306.02235. **abstract**.
26. Jin, J., Syrgkanis, V. (2023). Learning Causal Representations from General Environments: Identifiability and Intrinsic Ambiguity. arXiv:2311.12267. **abstract** [later venue unverified].
27. von Kügelgen, J., Besserve, M., Wendong, L., Gresele, L., Kekić, A., Bareinboim, E., Blei, D., Schölkopf, B. (2023). Nonparametric Identifiability of Causal Representations from Unknown Interventions. *NeurIPS 2023*. arXiv:2306.00542. **abstract**.
28. Jiang, Y., Aragam, B. (2023). Learning nonparametric latent causal graphs with unknown interventions. *NeurIPS 2023*. arXiv:2306.02899. **abstract**.
29. Zhang, J., Squires, C., Greenewald, K., Srivastava, A., Shanmugam, K., Uhler, C. (2023). Identifiability Guarantees for Causal Disentanglement from Soft Interventions. arXiv:2307.06250 (NeurIPS 2023 [venue unverified]). **abstract**.
30. Ahuja, K., Mahajan, D., Wang, Y., Bengio, Y. (2023). Interventional Causal Representation Learning. *ICML 2023*. arXiv:2209.11924. **abstract**.
31. Brehmer, J., de Haan, P., Lippe, P., Cohen, T. (2022). Weakly supervised causal representation learning. *NeurIPS 2022*. arXiv:2203.16437. **abstract**.
32. Saengkyongam, S., Rosenfeld, E., Ravikumar, P., Pfister, N., Peters, J. (2024). Identifying Representations for Intervention Extrapolation. *ICLR 2024*. arXiv:2310.04295. **abstract**.
33. Lachapelle, S., Rodríguez López, P., Sharma, Y., Everett, K., Le Priol, R., Lacoste, A., Lacoste-Julien, S. (2024/2026). Nonparametric Partial Disentanglement via Mechanism Sparsity: Sparse Actions, Interventions and Sparse Temporal Dependencies. arXiv:2401.04890 ; *JMLR* 2026. **abstract**.
34. Lachapelle, S., Rodríguez, P., Sharma, Y., Everett, K., Le Priol, R., Lacoste, A., Lacoste-Julien, S. (2022). Disentanglement via Mechanism Sparsity Regularization: A New Principle for Nonlinear ICA. *CLeaR 2022*. arXiv:2107.10098. **abstract** (snippet).
35. Lippe, P., Magliacane, S., Löwe, S., Asano, Y. M., Cohen, T., Gavves, E. (2022). CITRIS: Causal Identifiability from Temporal Intervened Sequences. *ICML 2022*. arXiv:2202.03169. **abstract**.
36. Lippe, P., et al. (2023). Causal Representation Learning for Instantaneous and Temporal Effects in Interactive Systems (iCITRIS). *ICLR 2023*. **background** [id/venue unverified].
37. Lippe, P., Magliacane, S., Löwe, S., Asano, Y. M., Cohen, T., Gavves, E. (2023). BISCUIT: Causal Representation Learning from Binary Interactions. *UAI 2023*. arXiv:2306.09643. **abstract**.
38. Yao, W., Sun, Y., Ho, A., Sun, C., Zhang, K. (2022). Learning Temporally Causal Latent Processes from General Temporal Data (LEAP). *ICLR 2022*. arXiv:2110.05428. **metadata**.
39. Yao, W., Chen, G., Zhang, K. (2022). Temporally Disentangled Representation Learning (TDRL). *NeurIPS 2022*. **metadata**.
40. Rajendran, G., Reizinger, P., Brendel, W., Ravikumar, P. (2024). An Interventional Perspective on Identifiability in Gaussian LTI Systems with Independent Component Analysis. *CLeaR 2024*. arXiv:2311.18048. **abstract**.
41. Zhang, C., Xie, Y. (2024). Identifiable Representation and Model Learning for Latent Dynamic Systems. arXiv:2410.17882. **abstract** (preprint).
42. Yao, D., Muller, C., Locatello, F. (2024). Marrying Causal Representation Learning with Dynamical Systems for Science. *NeurIPS 2024*. arXiv:2405.13888. **abstract**.
43. Yao, D., Rancati, D., Cadei, R., Fumero, M., Locatello, F. (2025). Unifying Causal Representation Learning with the Invariance Principle. *ICLR 2025*. arXiv:2409.02772. **abstract**.
44. Gamella, J. L., Bing, S., Runge, J. (2025). Sanity Checking Causal Representation Learning on a Simple Real-World System. arXiv:2502.20099. **abstract**.
45. Rubenstein, P. K., Weichwald, S., Bongers, S., Mooij, J. M., Janzing, D., Grosse-Wentrup, M., Schölkopf, B. (2017). Causal Consistency of Structural Equation Models. *UAI 2017*. arXiv:1707.00819. **abstract** (the definition is stated from background [std]).
46. Beckers, S., Halpern, J. Y. (2019). Abstracting Causal Models. *AAAI 2019*, 2678-2685. arXiv:1812.03789. **abstract**.
47. Beckers, S., Eberhardt, F., Halpern, J. Y. (2019). Approximate Causal Abstraction. *UAI 2019*, PMLR 115. https://pmc.ncbi.nlm.nih.gov/articles/PMC6779476/. **metadata**.
48. Rischel, E. F., Weichwald, S. (2021). Compositional Abstraction Error and a Category of Causal Models. *UAI 2021*, PMLR 161. arXiv:2103.15758. **abstract**.
49. Zennaro, F. M., Drávucz, M., Apachitei, G., Widanage, W. D., Damoulas, T. (2023). Jointly Learning Consistent Causal Abstractions Over Multiple Interventional Distributions. *CLeaR 2023*, PMLR 213:88-121. arXiv:2301.05893 ; code https://github.com/FMZennaro/CausalAbstraction. **abstract**.
50. Geiger, A., Wu, Z., Lu, H., Rozner, J., Kreiss, E., Icard, T., Goodman, N. D., Potts, C. (2022). Inducing Causal Structure for Interpretable Neural Networks. *ICML 2022* [venue unverified]. arXiv:2112.00826. **abstract**.
51. Geiger, A., Wu, Z., Potts, C., Icard, T., Goodman, N. D. (2024). Finding Alignments Between Interpretable Causal Variables and Distributed Neural Representations (DAS). arXiv:2303.02536 [venue unverified]. **abstract**.
52. Geiger, A., Ibeling, D., Zur, A., Chaudhary, M., Chauhan, S., Huang, J., Arora, A., Wu, Z., Goodman, N., Potts, C., Icard, T. (2023-2025). Causal Abstraction: A Theoretical Foundation for Mechanistic Interpretability. arXiv:2301.04709 (v4) [JMLR version unverified]. **abstract**.
53. Chalupka, K., Eberhardt, F., Perona, P. (2016). Multi-Level Cause-Effect Systems. *AISTATS 2016*, PMLR 51:361-369. **metadata**. Also: Causal feature learning: an overview, *Behaviormetrika* 2017. **metadata**.
54. Méloux, M., Pimentel, T., Portet, F., Peyrard, M. (2026). Validating Causal Abstraction Metrics on Simulated Complex Systems. arXiv:2607.00267. **abstract**.

## Area 3: System identification with inputs

55. Proctor, J. L., Brunton, S. L., Kutz, J. N. (2016). Dynamic mode decomposition with control. *SIAM J. Appl. Dyn. Syst.* 15(1):142-161. doi:10.1137/15M1013857 ; arXiv:1409.6358. **abstract**.
56. Proctor, J. L., Brunton, S. L., Kutz, J. N. (2018). Generalizing Koopman theory to allow for inputs and control. *SIAM J. Appl. Dyn. Syst.* 17(1):909-930. doi:10.1137/16M1062296 ; arXiv:1602.07647. **metadata**.
57. Korda, M., Mezić, I. (2018). Linear predictors for nonlinear dynamical systems: Koopman operator meets model predictive control. *Automatica* 93:149-160. arXiv:1611.03537. **abstract**.
58. Williams, M. O., Kevrekidis, I. G., Rowley, C. W. (2015). A data-driven approximation of the Koopman operator: Extending dynamic mode decomposition. *J. Nonlinear Sci.* 25(6):1307-1346. doi:10.1007/s00332-015-9258-5. **metadata**.
59. Askham, T., Kutz, J. N. (2018). Variable projection methods for an optimized dynamic mode decomposition. *SIAM J. Appl. Dyn. Syst.* 17(1):380-416. **metadata**.
60. Sashidhar, D., Kutz, J. N. (2022). Bagging, optimized dynamic mode decomposition for robust, stable forecasting with spatial and temporal uncertainty quantification. *Phil. Trans. R. Soc. A* 380:20210199. arXiv:2107.10878. **metadata**.
61. Bruder, D., Fu, X., Vasudevan, R. (2021). Advantages of bilinear Koopman realizations for the modeling and control of systems with unknown dynamics. *IEEE RA-L* 6(3):4369-4376. arXiv:2010.09961. **abstract**.
62. Nüske, F., Peitz, S., Philipp, F., Schaller, M., Worthmann, K. (2023). Finite-data error bounds for Koopman-based prediction and control. *J. Nonlinear Sci.* 33:14. arXiv:2108.07102. **metadata**.
63. Strässer, R., Worthmann, K., Mezić, I., Berberich, J., Schaller, M., Allgöwer, F. (2026). An overview of Koopman-based control: From error bounds to closed-loop guarantees. *Annual Reviews in Control* 61. arXiv:2509.02839. **abstract**.
64. Shang, X., Haseli, M., Cortés, J., Zheng, Y. (2026). On the existence of Koopman linear embeddings for controlled nonlinear systems. arXiv:2602.14537. **abstract**.
65. Abudia, M., Rosenfeld, J. A., Kamalapurkar, R. (2025). On dynamic mode decomposition of control-affine systems. arXiv:2503.10891. **abstract**.
66. Han, Y., Hao, W., Vaidya, U. (2020). Deep learning of Koopman representation for control. *IEEE CDC 2020*, 1890-1895. arXiv:2010.07546. **metadata**.
67. Brunton, S. L., Proctor, J. L., Kutz, J. N. (2016). Sparse identification of nonlinear dynamics with control (SINDYc). *IFAC-PapersOnLine* 49(18):710-715. arXiv:1605.06682. **abstract**.
68. Kaiser, E., Kutz, J. N., Brunton, S. L. (2018). Sparse identification of nonlinear dynamics for model predictive control in the low-data limit. *Proc. R. Soc. A* 474:20180335. **metadata**.
69. Fasel, U., Kutz, J. N., Brunton, B. W., Brunton, S. L. (2022). Ensemble-SINDy: Robust sparse model discovery in the low-data, high-noise limit, with active learning and control. arXiv:2111.10992 [journal venue unverified]. **metadata**.
70. Van Overschee, P., De Moor, B. (1994). N4SID: Subspace algorithms for the identification of combined deterministic-stochastic systems. *Automatica* 30(1):75-93. doi:10.1016/0005-1098(94)90230-5. **metadata**.
71. Verhaegen, M., Dewilde, P. (1992). Subspace model identification, Parts 1 and 2. *Int. J. Control* 56(5):1187-1210, 1211-1241. **metadata**.
72. Larimore, W. E. (1990). Canonical variate analysis in identification, filtering, and adaptive control. *IEEE CDC 1990*, 596-604. doi:10.1109/CDC.1990.203665. **metadata**.
73. Chiuso, A. (2007). The role of vector autoregressive modeling in predictor-based subspace identification. *Automatica* 43(6):1034-1048. **metadata**.
74. Cox, P. B., Tóth, R. (2021). Linear parameter-varying subspace identification: A unified framework. *Automatica*. arXiv:2008.03347. **abstract**.
75. Sani, O. G., Abbaspourazad, H., Wong, Y. T., Pesaran, B., Shanechi, M. M. (2021). Modeling behaviorally relevant neural dynamics enabled by preferential subspace identification. *Nature Neuroscience* 24:140-149. **metadata** (method description only).
76. Vahidi, P., Sani, O. G., Shanechi, M. M. (2024). Modeling and dissociation of intrinsic and input-driven neural population dynamics underlying behavior. *PNAS* 121(7):e2212887121. doi:10.1073/pnas.2212887121 ; bioRxiv 10.1101/2023.03.14.532554. **full** (preprint methods).
77. Sattar, Y., Oymak, S., Ozay, N. (2022). Finite sample identification of bilinear dynamical systems. arXiv:2208.13915. **abstract**.
78. Sattar, Y., Jedra, Y., Fazel, M., Dean, S. (2025). Finite sample identification of partially observed bilinear dynamical systems. arXiv:2501.07652. **abstract**.
79. Willems, J. C., Rapisarda, P., Markovsky, I., De Moor, B. (2005). A note on persistency of excitation. *Systems & Control Letters* 54(4):325-329. doi:10.1016/j.sysconle.2004.09.003. **abstract**.
80. De Persis, C., Tesi, P. (2020). Formulas for data-driven control: Stabilization, optimality, and robustness. *IEEE TAC* 65(3):909-924. **metadata**.
81. van Waarde, H. J., Eising, J., Camlibel, M. K., Trentelman, H. L. (2023). The informativity approach to data-driven analysis and control. arXiv:2302.10488. **abstract**.
82. Camlibel, M. K., van Waarde, H. J., Rapisarda, P. (2024). The shortest experiment for linear system identification. arXiv:2407.12509. **abstract**.
83. Moore, B. C. (1981). Principal component analysis in linear systems: Controllability, observability, and model reduction. *IEEE TAC* 26(1):17-32. doi:10.1109/TAC.1981.1102568. **metadata**.
84. Lall, S., Marsden, J. E., Glavaški, S. (2002). A subspace approach to balanced truncation for model reduction of nonlinear control systems. *Int. J. Robust Nonlinear Control* 12(6):519-535. doi:10.1002/rnc.657. **metadata**.
85. Rowley, C. W. (2005). Model reduction for fluids, using balanced proper orthogonal decomposition. *Int. J. Bifurcation and Chaos* 15(3):997-1013. doi:10.1142/S0218127405012429. **abstract**.
86. Himpe, C. (2018). emgr - The empirical Gramian framework. *Algorithms* 11(7):91. doi:10.3390/a11070091 ; and emgr v5.99, *ACM TOMS* 2023, doi:10.1145/3609860, arXiv:2209.03833 ; https://github.com/gramian/emgr (BSD-2, archived). **abstract + docs**.
87. Krener, A. J., Ide, K. (2009). Measures of unobservability. *IEEE CDC 2009*, 6401-6406. **metadata**.
88. Burohman, A. M., Besselink, B., Scherpen, J. M. A., Camlibel, M. K. (2021). From data to reduced-order models via generalized balanced truncation. arXiv:2109.11685. **abstract**.
89. Gutenkunst, R. N., Waterfall, J. J., Casey, F. P., Brown, K. S., Myers, C. R., Sethna, J. P. (2007). Universally sloppy parameter sensitivities in systems biology models. *PLoS Comput. Biol.* 3(10):e189. doi:10.1371/journal.pcbi.0030189. **metadata** (used for methodology only).
90. Transtrum, M. K., Machta, B. B., Brown, K. S., Daniels, B. C., Myers, C. R., Sethna, J. P. (2015). Perspective: Sloppiness and emergent theories in physics, biology, and beyond. *J. Chem. Phys.* 143:010901. arXiv:1501.07668. **metadata**.
91. Bellman, R., Åström, K. J. (1970). On structural identifiability. *Math. Biosci.* 7:329-339. **metadata**.
92. Simchowitz, M., Mania, H., Tu, S., Jordan, M. I., Recht, B. (2018). Learning without mixing: Towards a sharp analysis of linear system identification. *COLT 2018*. arXiv:1802.08334. **abstract**.
93. Oymak, S., Ozay, N. (2019). Non-asymptotic identification of LTI systems from a single trajectory. *ACC 2019*, 5655-5661. arXiv:1806.05722. **metadata**.
94. Tsiamis, A., Pappas, G. J. (2019). Finite sample analysis of stochastic system identification. *IEEE CDC 2019*, 3648-3654. **metadata**.
95. Tu, S., Frostig, R., Soltanolkotabi, M. (2022). Learning from many trajectories. arXiv:2203.17193 [journal version unverified]. **abstract**.
96. Ziemann, I., Tsiamis, A., Lee, B., Jedra, Y., Matni, N., Pappas, G. J. (2023). A tutorial on the non-asymptotic theory of system identification. *IEEE CDC 2023*, 8921-8939. arXiv:2309.03873. **abstract**.
97. He, J., Ziemann, I., Rojas, C. R., Qin, S. J., Hjalmarsson, H. (2025). Finite sample analysis of open-loop subspace identification methods. arXiv:2501.16639. **abstract**.
98. PyDMD. https://github.com/PyDMD/PyDMD, MIT. Demo, N., Tezzele, M., Rozza, G. (2018), *JOSS* doi:10.21105/joss.00530 ; Ichinaga, S. M., et al. (2024), arXiv:2402.07463. **docs + abstract**.
99. PyKoopman. https://github.com/dynamicslab/pykoopman, MIT. Pan, S., et al. (2024), *JOSS* doi:10.21105/joss.05881. **docs**.
100. pysindy. https://github.com/dynamicslab/pysindy, MIT. **docs**.
101. nfoursid. https://github.com/spmvg/nfoursid, MIT. **docs**.
102. SIPPY. https://github.com/CPCLAB-UNIPI/SIPPY, LGPL (per README). **metadata**.
103. PyPSID. https://github.com/ShanechiLab/PyPSID, USC academic / non-commercial licence. **docs (LICENSE)**.

## Area 4: Neural latent dynamical models with inputs

104. Krishnan, R. G., Shalit, U., Sontag, D. (2015). Deep Kalman Filters. arXiv:1511.05121. **abstract**.
105. Krishnan, R. G., Shalit, U., Sontag, D. (2017). Structured Inference Networks for Nonlinear State Space Models. *AAAI 2017*. arXiv:1609.09869. **abstract**.
106. Hafner, D., Lillicrap, T., Fischer, I., Villegas, R., Ha, D., Lee, H., Davidson, J. (2019). Learning Latent Dynamics for Planning from Pixels (PlaNet). *ICML 2019*. arXiv:1811.04551. **abstract**.
107. Hafner, D., Lillicrap, T., Ba, J., Norouzi, M. (2020). Dream to Control: Learning Behaviors by Latent Imagination. *ICLR 2020*. arXiv:1912.01603. **abstract**.
108. Chen, R. T. Q., Rubanova, Y., Bettencourt, J., Duvenaud, D. (2018). Neural Ordinary Differential Equations. *NeurIPS 2018*. arXiv:1806.07366. **abstract**.
109. Rubanova, Y., Chen, R. T. Q., Duvenaud, D. (2019). Latent ODEs for Irregularly-Sampled Time Series. *NeurIPS 2019*. arXiv:1907.03907. **abstract**.
110. Kidger, P., Morrill, J., Foster, J., Lyons, T. (2020). Neural Controlled Differential Equations for Irregular Time Series. *NeurIPS 2020*. arXiv:2005.08926. **abstract**.
111. Li, X., Wong, T.-K. L., Chen, R. T. Q., Duvenaud, D. (2020). Scalable Gradients for Stochastic Differential Equations. *AISTATS 2020*. arXiv:2001.01328. **abstract**.
112. Jia, J., Benson, A. R. (2019). Neural Jump Stochastic Differential Equations. *NeurIPS 2019*. arXiv:1905.10403. **abstract**.
113. Johnson, M. J., Duvenaud, D., Wiltschko, A. B., Adams, R. P., Datta, S. R. (2016). Composing graphical models with neural networks for structured representations and fast inference. *NeurIPS 2016*. arXiv:1603.06277. **abstract**.
114. Valente, A., Pillow, J. W., Ostojic, S. (2022). Extracting computational mechanisms from neural data using low-rank RNNs. *NeurIPS 2022*. **abstract**.
115. Pals, M., Sağtekin, A. E., Pei, F., Gloeckler, M., Macke, J. H. (2024). Inferring stochastic low-rank recurrent neural networks from neural data. *NeurIPS 2024*. arXiv:2406.16749. **abstract**.
116. Bialek, W., Nemenman, I., Tishby, N. (2001). Predictability, Complexity, and Learning. *Neural Computation* 13:2409-2463. arXiv:physics/0007070. **abstract**.
117. Creutzig, F., Globerson, A., Tishby, N. (2009). Past-future information bottleneck in dynamical systems. *Phys. Rev. E* 79:041925. doi:10.1103/PhysRevE.79.041925. **abstract** (snippet).
118. Alemi, A. A., Fischer, I., Dillon, J. V., Murphy, K. (2017). Deep Variational Information Bottleneck. *ICLR 2017*. arXiv:1612.00410. **abstract**.
119. van den Oord, A., Li, Y., Vinyals, O. (2018). Representation Learning with Contrastive Predictive Coding. arXiv:1807.03748. **abstract**.
120. Schneider, S., Lee, J. H., Mathis, M. W. (2023). Learnable latent embeddings for joint behavioural and neural analysis (CEBRA). *Nature* 617:360-368 [pages unverified]. arXiv:2204.00673. **abstract**.
121. Lakshminarayanan, B., Pritzel, A., Blundell, C. (2017). Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles. *NeurIPS 2017*. arXiv:1612.01474. **abstract**.
122. Chua, K., Calandra, R., McAllister, R., Levine, S. (2018). Deep Reinforcement Learning in a Handful of Trials using Probabilistic Dynamics Models (PETS). *NeurIPS 2018*. arXiv:1805.12114. **abstract**.
123. LeCun, Y. (2022). A Path Towards Autonomous Machine Intelligence (v0.9.2). OpenReview https://openreview.net/pdf?id=BZ5a1r-kVsf. **metadata** (snippets).
124. Assran, M., et al. (2025). V-JEPA 2: Self-Supervised Video Models Enable Understanding, Prediction and Planning. arXiv:2506.09985. **full** (action-conditioned section).
125. Lei, A., Schölkopf, B., Posner, I. (2022). Variational Causal Dynamics: Discovering Modular World Models from Interventions. arXiv:2206.11131. **abstract**.
126. Kim, K. W. (2026). Latent State Design for World Models under Sufficiency Constraints. arXiv:2605.01694. **abstract**.
127. Buisson-Fenet, M., Morgenthaler, V., Trimpe, S., Di Meglio, F. (2022). Recognition Models to Learn Dynamics from Partial Observations with Neural ODEs. arXiv:2205.12550 [TMLR venue unverified]. **abstract**.
128. Perez, E., Strub, F., de Vries, H., Dumoulin, V., Courville, A. (2018). FiLM: Visual Reasoning with a General Conditioning Layer. *AAAI 2018*. arXiv:1709.07871. **abstract**.

## Area 5: Optimal and active experiment design

129. Chaloner, K., Verdinelli, I. (1995). Bayesian Experimental Design: A Review. *Statistical Science* 10(3):273-304. doi:10.1214/ss/1177009939. **metadata**.
130. Ryan, E. G., Drovandi, C. C., McGree, J. M., Pettitt, A. N. (2016). A Review of Modern Computational Algorithms for Bayesian Optimal Design. *Int. Stat. Review* 84(1):128-154. doi:10.1111/insr.12107. **abstract**.
131. Rainforth, T., Foster, A., Ivanova, D. R., Bickford Smith, F. (2024). Modern Bayesian Experimental Design. *Statistical Science* 39(1):100-114. doi:10.1214/23-STS915 ; arXiv:2302.14545. **full**.
132. Rainforth, T., Cornish, R., Yang, H., Warrington, A., Wood, F. (2018). On Nesting Monte Carlo Estimators. *ICML 2018*, PMLR 80:4267-4276. arXiv:1709.06181. **abstract**.
133. Foster, A., Jankowiak, M., Bingham, E., Horsfall, P., Teh, Y. W., Rainforth, T., Goodman, N. (2019). Variational Bayesian Optimal Experimental Design. *NeurIPS 2019*. arXiv:1903.05480. **abstract**.
134. Foster, A., Jankowiak, M., O'Meara, M., Teh, Y. W., Rainforth, T. (2020). A Unified Stochastic Gradient Approach to Designing Bayesian-Optimal Experiments. *AISTATS 2020*, PMLR 108:2959-2969. arXiv:1911.00294. **abstract**.
135. Foster, A., Ivanova, D. R., Malik, I., Rainforth, T. (2021). Deep Adaptive Design: Amortizing Sequential Bayesian Experimental Design. *ICML 2021*, PMLR 139. arXiv:2103.02438 ; code https://github.com/ae-foster/dad. **abstract**.
136. Ivanova, D. R., Foster, A., Kleinegesse, S., Gutmann, M. U., Rainforth, T. (2021). Implicit Deep Adaptive Design: Policy-Based Experimental Design without Likelihoods. *NeurIPS 2021*. arXiv:2111.02329. **abstract**.
137. Kleinegesse, S., Gutmann, M. U. (2021). Gradient-based Bayesian Experimental Design for Implicit Models using Mutual Information Lower Bounds. arXiv:2105.04379. **abstract**.
138. Pérez-Vieites, S., Iqbal, S., Särkkä, S., Baumann, D. (2025). Online Bayesian Experimental Design for Partially Observed Dynamical Systems. arXiv:2511.04403. **abstract**.
139. Seung, H. S., Opper, M., Sompolinsky, H. (1992). Query by Committee. *COLT 1992*, 287-294. doi:10.1145/130385.130417. **abstract**.
140. Houlsby, N., Huszár, F., Ghahramani, Z., Lengyel, M. (2011). Bayesian Active Learning for Classification and Preference Learning. arXiv:1112.5745. **abstract**.
141. Bickford Smith, F., Kirsch, A., Farquhar, S., Gal, Y., Foster, A., Rainforth, T. (2023). Prediction-Oriented Bayesian Active Learning (EPIG). *AISTATS 2023*, PMLR 206. arXiv:2304.08151 ; code https://github.com/fbickfordsmith/epig. **abstract**.
142. Pathak, D., Gandhi, D., Gupta, A. (2019). Self-Supervised Exploration via Disagreement. *ICML 2019*. arXiv:1906.04161. **abstract**.
143. Shyam, P., Jaśkowski, W., Gomez, F. (2019). Model-Based Active Exploration. *ICML 2019*, PMLR 97:5779-5788. arXiv:1810.12162. **abstract**.
144. Sukhija, B., Treven, L., Sancaktar, C., Blaes, S., Coros, S., Krause, A. (2023). Optimistic Active Exploration of Dynamical Systems. arXiv:2306.12371 [NeurIPS venue unverified]. **abstract**.
145. Mehra, R. K. (1974). Optimal input signals for parameter estimation in dynamic systems - Survey and new results. *IEEE TAC* 19(6):753-768. **metadata** [DOI unverified].
146. Goodwin, G. C., Payne, R. L. (1977). *Dynamic System Identification: Experiment Design and Data Analysis*. Academic Press. **metadata**.
147. Pronzato, L. (2008). Optimal experimental design and some related control problems. *Automatica* 44:303-325. arXiv:0802.4381. **abstract**.
148. Gevers, M. (2005). Identification for Control: From the Early Achievements to the Revival of Experiment Design. *European J. Control* 11(4-5):335-352. **abstract**.
149. Hjalmarsson, H. (2005). From experiment design to closed-loop control. *Automatica* 41(3):393-438 ; and (2009) System identification of complex and structured systems. *European J. Control* 15(3-4):275-310. **metadata**.
150. Manchester, I. R. (2010). Input Design for System Identification via Convex Relaxation. arXiv:1009.5614 (IEEE CDC 2010). **abstract**.
151. Wilson, A. D., Schultz, J. A., Murphey, T. D. (2014). Trajectory Synthesis for Fisher Information Maximization. *IEEE T-RO* 30(6):1358-1370. arXiv:1709.03426. **abstract**.
152. Wagenmaker, A., Jamieson, K. (2020). Active Learning for Identification of Linear Dynamical Systems. *COLT 2020*, PMLR 125:3487-3582. arXiv:2002.00495. **abstract**.
153. Wagenmaker, A., Simchowitz, M., Jamieson, K. (2021). Task-Optimal Exploration in Linear Dynamical Systems. *ICML 2021*, PMLR 139:10641-10652. arXiv:2102.05214. **abstract**.
154. Mania, H., Jordan, M. I., Recht, B. (2022). Active Learning for Nonlinear System Identification with Guarantees. *JMLR* 23(32):1-30. arXiv:2006.10277. **abstract**.
155. Chatzikiriakos, N., Jamieson, K., Iannelli, A. (2026). High Effort, Low Gain: Fundamental Limits of Active Learning for Linear Dynamical Systems. *AISTATS 2026*. arXiv:2509.11907. **abstract**.
156. Blanke, M., Lelarge, M. (2022). Online Greedy Identification of Linear Dynamical Systems. arXiv:2204.06375. **abstract**.
157. van Waarde, H. J. (2021). Beyond Persistent Excitation: Online Experiment Design for Data-Driven Modeling and Control. arXiv:2102.11193. **abstract**.
158. Lewi, J., Butera, R., Paninski, L. (2009). Sequential Optimal Design of Neurophysiology Experiments. *Neural Computation* 21(3):619-687. **abstract** (methods only).
159. Shababo, B., Paige, B., Pakman, A., Paninski, L. (2013). Bayesian Inference and Online Experimental Design for Mapping Neural Microcircuits. *NIPS 2013*, 1304-1312. **abstract** (methods only).
160. Hauser, A., Bühlmann, P. (2014). Two optimal strategies for active learning of causal models from interventional data. *Int. J. Approx. Reasoning* 55(4):926-939. arXiv:1205.4174. **abstract**.
161. Kocaoglu, M., Dimakis, A. G., Vishwanath, S. (2017). Cost-Optimal Learning of Causal Graphs. *ICML 2017*, PMLR 70:1875-1884. arXiv:1703.02645. **abstract**.
162. Agrawal, R., Squires, C., Yang, K., Shanmugam, K., Uhler, C. (2019). ABCD-Strategy: Budgeted Experimental Design for Targeted Causal Structure Discovery. *AISTATS 2019*, PMLR 89:3400-3409. **abstract**.
163. Sussex, S., Uhler, C., Krause, A. (2021). Near-Optimal Multi-Perturbation Experimental Design for Causal Structure Learning. *NeurIPS 2021*. arXiv:2105.14024. **abstract**.
164. Tigas, P., Annadani, Y., Jesson, A., Schölkopf, B., Gal, Y., Bauer, S. (2022). Interventions, Where and How? Experimental Design for Causal Models at Scale. *NeurIPS 2022*. arXiv:2203.02016 ; code https://github.com/yannadani/cbed. **abstract**.
165. Box, G. E. P., Hill, W. J. (1967). Discrimination Among Mechanistic Models. *Technometrics* 9(1):57-71. doi:10.1080/00401706.1967.10490441. **abstract**.
166. Atkinson, A. C., Fedorov, V. V. (1975). The design of experiments for discriminating between two rival models. *Biometrika* 62(1):57-70 ; and Optimal design: Experiments for discriminating between several models. *Biometrika* 62(2):289-303. **metadata**.
167. Vanlier, J., Tiemann, C. A., Hilbers, P. A. J., van Riel, N. A. W. (2014). Optimal experiment design for model selection in biochemical networks. *BMC Systems Biology* 8:20. doi:10.1186/1752-0509-8-20. **abstract** (methods only).
168. Bania, P. (2019). Bayesian Input Design for Linear Dynamical Model Discrimination. *Entropy* 21(4):351. doi:10.3390/e21040351. **full**.
169. Letham, B., Letham, P. A., Rudin, C., Browne, E. P. (2016). Prediction uncertainty and optimal experimental design for learning dynamical systems. *Chaos* 26:063110. arXiv:1511.03395. **abstract**.
170. Ljung, L. (1999). *System Identification: Theory for the User*, 2nd ed. Prentice Hall. **background**.
171. Pintelon, R., Schoukens, J. (2012). *System Identification: A Frequency Domain Approach*, 2nd ed. Wiley/IEEE Press. **background**.
172. Schoukens, J., Ljung, L. (2019). Nonlinear System Identification: A User-Oriented Roadmap. arXiv:1902.00683. **abstract**.
173. Kirsch, A., van Amersfoort, J., Gal, Y. (2019). BatchBALD: Efficient and Diverse Batch Acquisition for Deep Bayesian Active Learning. *NeurIPS 2019*. arXiv:1906.08158. **abstract**.
174. Kirsch, A., Farquhar, S., Atighehchian, P., Jesson, A., Branchaud-Charron, F., Gal, Y. (2023). Stochastic Batch Acquisition: A Simple Baseline for Deep Active Learning. *TMLR*. arXiv:2106.12059. **abstract**.
175. Ash, J. T., Zhang, C., Krishnamurthy, A., Langford, J., Agarwal, A. (2020). Deep Batch Active Learning by Diverse, Uncertain Gradient Lower Bounds (BADGE). *ICLR 2020*. arXiv:1906.03671. **abstract**.
176. Kirsch, A., Gal, Y. (2022). Unifying Approaches in Active Learning and Active Sampling via Fisher Information and Information-Theoretic Quantities. *TMLR*. arXiv:2208.00549. **abstract**.
177. Krause, A., Singh, A., Guestrin, C. (2008). Near-Optimal Sensor Placements in Gaussian Processes. *JMLR* 9:235-284 [pages unverified]. **abstract**.
178. Snoek, J., Larochelle, H., Adams, R. P. (2012). Practical Bayesian Optimization of Machine Learning Algorithms. *NeurIPS 2012*. **metadata**.
179. Lee, E. H., Perrone, V., Archambeau, C., Seeger, M. (2020). Cost-aware Bayesian Optimization. arXiv:2003.10870. **abstract**.
180. Mittal, S., Tatarchenko, M., Çiçek, Ö., Brox, T. (2019). Parting with Illusions about Deep Active Learning. arXiv:1912.05361. **abstract**.
181. Munjal, P., Hayat, N., Hayat, M., Sourati, J., Khan, S. (2022). Towards Robust and Reproducible Active Learning using Neural Networks. *CVPR 2022*, 223-232. arXiv:2002.09564. **abstract**.
182. Lüth, C. T., Bungert, T. J., Klein, L., Jaeger, P. F. (2023). Navigating the Pitfalls of Active Learning Evaluation: A Systematic Framework for Meaningful Performance Assessment. *NeurIPS 2023*. arXiv:2301.10625. **full** (pitfalls section).
183. Agarwal, R., Schwarzer, M., Castro, P. S., Courville, A., Bellemare, M. G. (2021). Deep Reinforcement Learning at the Edge of the Statistical Precipice. *NeurIPS 2021*. arXiv:2108.13264. **abstract**.

## Area 6: State equivalence and closure

184. Shalizi, C. R., Crutchfield, J. P. (2001). Computational Mechanics: Pattern and Prediction, Structure and Simplicity. *J. Stat. Phys.* 104:817-879. arXiv:cond-mat/9907176. **abstract**.
185. Barnett, N., Crutchfield, J. P. (2015). Computational Mechanics of Input-Output Processes: Structured Transformations and the ε-Transducer. *J. Stat. Phys.* 161:404-451. doi:10.1007/s10955-015-1327-5 ; arXiv:1412.2690. **abstract**.
186. Shalizi, C. R., Shalizi, K. L., Crutchfield, J. P. (2002). An Algorithm for Pattern Discovery in Time Series (CSSR). arXiv:cs/0210025. **abstract**.
187. Littman, M. L., Sutton, R. S., Singh, S. (2001). Predictive Representations of State. *NIPS 14*. **abstract**.
188. Boots, B., Siddiqi, S. M., Gordon, G. J. (2011). Closing the Learning-Planning Loop with Predictive State Representations. *IJRR* 30(7). arXiv:0912.2385. **metadata**.
189. Boots, B., Gretton, A., Gordon, G. J. (2013). Hilbert Space Embeddings of Predictive State Representations. *UAI 2013*. arXiv:1309.6819. **metadata** (title).
190. Givan, R., Dean, T., Greig, M. (2003). Equivalence notions and model minimization in Markov decision processes. *Artificial Intelligence* 147(1-2):163-223. doi:10.1016/S0004-3702(02)00376-4. **metadata**.
191. Ferns, N., Panangaden, P., Precup, D. (2004). Metrics for Finite Markov Decision Processes. *UAI 2004*, 162-169. arXiv:1207.4114. **abstract**.
192. Castro, P. S., Kastner, T., Panangaden, P., Rowland, M. (2021). MICo: Improved representations via sampling-based state similarity for Markov decision processes. *NeurIPS 2021*. arXiv:2106.08229. **metadata**.
193. Zhang, A., McAllister, R., Calandra, R., Gal, Y., Levine, S. (2021). Learning Invariant Representations for Reinforcement Learning without Reconstruction (DBC). *ICLR 2021*. arXiv:2006.10742. **abstract**.
194. Li, L., Walsh, T. J., Littman, M. L. (2006). Towards a Unified Theory of State Abstraction for MDPs. *ISAIM 2006*. **metadata**.
195. Abel, D., Hershkowitz, D. E., Littman, M. L. (2016). Near Optimal Behavior via Approximate State Abstraction. *ICML 2016*, PMLR 48:2915-2923. **metadata**.
196. Subramanian, J., Sinha, A., Seraj, R., Mahajan, A. (2022). Approximate Information State for Approximate Planning and Reinforcement Learning in Partially Observed Systems. *JMLR* 23(12):1-83. **abstract**.
197. Rosas, F. E., Geiger, B. C., Luppi, A. I., Seth, A. K., Polani, D., Gastpar, M., Mediano, P. A. M. (2024). Software in the natural world: A computational approach to hierarchical emergence. arXiv:2402.09090. **abstract**.
198. Shi, C., Wan, R., Song, R., Lu, W., Leng, L. (2020). Does the Markov Decision Process Fit the Data: Testing for the Markov Property in Sequential Decision Making. arXiv:2002.01751 [ICML 2020 venue unverified]. **abstract**.
199. Shah, R. D., Peters, J. (2020). The Hardness of Conditional Independence Testing and the Generalised Covariance Measure. *Annals of Statistics* 48(3). arXiv:1804.07203. **abstract**.
200. Zhang, K., Peters, J., Janzing, D., Schölkopf, B. (2011). Kernel-based Conditional Independence Test and Application in Causal Discovery. *UAI 2011*, 804-813. arXiv:1202.3775. **metadata**.
201. Runge, J. (2018). Conditional independence testing based on a nearest-neighbor estimator of conditional mutual information. *AISTATS 2018*, PMLR 84:938-947. arXiv:1709.01447. **metadata**.
202. Manten, G., Casolo, C., Ferrucci, E., Mogensen, S. W., Salvi, C., Kilbertus, N. (2024). Signature Kernel Conditional Independence Tests in Causal Discovery for Stochastic Processes. arXiv:2402.18477. **abstract**.
203. Schreiber, T. (2000). Measuring information transfer. *Phys. Rev. Lett.* 85(2):461-464. arXiv:nlin/0001042. **metadata**.
204. Pearl, J. (2001). Direct and Indirect Effects. *UAI 2001*, 411-420. arXiv:1301.2300. **metadata**.
205. Imai, K., Keele, L., Tingley, D. (2010). A General Approach to Causal Mediation Analysis. *Psychological Methods* 15(4):309-334. **metadata**.
206. Luo, L., Shi, C., Wang, J., Wu, Z., Li, L. (2023/2025). Multivariate Dynamic Mediation Analysis under a Reinforcement Learning Framework. arXiv:2310.16203. **abstract**.
207. [Authors not recorded] (2024). Continuous-time mediation analysis for repeatedly measured mediators and outcomes. arXiv:2403.11017. **metadata** (snippet).

## Area 7: Lifting / inverse problems / model-based stimulation design

208. Kalman, R. E., Ho, Y. C., Narendra, K. S. (1963). Controllability of linear dynamical systems. *Contributions to Differential Equations* 1:189-213. **background** [bibliographic details unverified].
209. Liu, Y.-Y., Slotine, J.-J., Barabási, A.-L. (2011). Controllability of complex networks. *Nature* 473:167-173. doi:10.1038/nature10011. **abstract**.
210. Pasqualetti, F., Zampieri, S., Bullo, F. (2014). Controllability Metrics, Limitations and Algorithms for Complex Networks. *IEEE TCNS* 1(1):40-52. arXiv:1308.1201. **abstract**.
211. Yan, G., Ren, J., Lai, Y.-C., Lai, C.-H., Li, B. (2012). Controlling complex networks: How much energy is needed? *Phys. Rev. Lett.* 108:218703. **metadata**.
212. Yan, G., Tsekenis, G., Barzel, B., Slotine, J.-J., Liu, Y.-Y., Barabási, A.-L. (2015). Spectrum of controlling and observing complex networks. *Nature Physics* 11:779-786. arXiv:1503.01160. **metadata** (title only).
213. Summers, T. H., Cortesi, F. L., Lygeros, J. (2016). On Submodularity and Controllability in Complex Dynamical Networks. *IEEE TCNS* 3(1):91-101. arXiv:1404.7665. **abstract** (a published correction exists; its scope is [unverified]).
214. Nagahara, M., Quevedo, D. E., Nešić, D. (2013/2016). Maximum-Hands-Off Control and L1 Optimality. *IEEE CDC 2013* / *IEEE TAC* 61(3) [journal detail unverified]. arXiv:1307.8232. **abstract**.
215. Li, W., Todorov, E. (2004). Iterative Linear Quadratic Regulator Design for Nonlinear Biological Movement Systems. *ICINCO 2004*, 222-229. doi:10.5220/0001143902220229. **abstract** (methods only).
216. Watter, M., Springenberg, J. T., Boedecker, J., Riedmiller, M. (2015). Embed to Control: A Locally Linear Latent Dynamics Model for Control from Raw Images. *NeurIPS 2015*. arXiv:1506.07365. **abstract**.
217. Bolus, M. F., Willats, A. A., Rozell, C. J., Stanley, G. B. (2021). State-space optimal feedback control of optogenetically driven neural activity. *J. Neural Engineering* 18(3):036006. doi:10.1088/1741-2552/abb89c. **abstract** (methods only).
218. Yang, Y., Qiao, S., Sani, O. G., Sedillo, J. I., Ferrentino, B., Pesaran, B., Shanechi, M. M. (2021). Modelling and prediction of the dynamic responses of large-scale brain networks during direct electrical stimulation. *Nature Biomedical Engineering* 5. doi:10.1038/s41551-020-00666-w. **abstract** (methods only).
219. Fehrman, C., Meliza, C. D. (2024/2025). Model Predictive Control on the Neural Manifold. arXiv:2406.14801 ; *Neural Computation* 37(12). **abstract**.
220. De, A., Kiani, R., Mazzucato, L. (2026). Towards model-based design of causal manipulations of brain circuits with high spatiotemporal precision. *Current Opinion in Behavioral Sciences* 67:101632. arXiv:2505.24790. **full** (methods content only).
221. Hansen, N. (2016). The CMA Evolution Strategy: A Tutorial. arXiv:1604.00772. **abstract**.
222. python-control (BSD-3), cvxpy / OSQP (Apache-2.0), pycma: software **docs/background**; licences [unverified].

## Area 8: Uncertainty, calibration, abstention

223. Chow, C. K. (1970). On optimum recognition error and reject tradeoff. *IEEE Trans. Inf. Theory* 16(1):41-46. doi:10.1109/TIT.1970.1054406. **abstract**.
224. El-Yaniv, R., Wiener, Y. (2010). On the Foundations of Noise-free Selective Classification. *JMLR* 11:1605-1641. **abstract**.
225. Geifman, Y., El-Yaniv, R. (2017). Selective Classification for Deep Neural Networks. *NeurIPS 2017*. arXiv:1705.08500. **abstract**.
226. Angelopoulos, A. N., Bates, S. (2021/2023). A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification. arXiv:2107.07511. **abstract**.
227. Stankevičiūtė, K., Alaa, A. M., van der Schaar, M. (2021). Conformal Time-series Forecasting. *NeurIPS 2021*. code https://github.com/kamilest/conformal-rnn. **abstract**.
228. Cleaveland, M., Lee, I., Pappas, G. J., Lindemann, L. (2024). Conformal Prediction Regions for Time Series using Linear Complementarity Programming. *AAAI 2024*. arXiv:2304.01075. **abstract**.
229. Sun, S. H., Yu, R. (2024). Copula Conformal Prediction for Multi-step Time Series Forecasting. *ICLR 2024*. arXiv:2212.03281. **abstract**.
230. Xu, C., Xie, Y. (2021). Conformal prediction interval for dynamic time-series (EnbPI). *ICML 2021*, PMLR 139. arXiv:2010.09107. **abstract**.
231. Gibbs, I., Candès, E. J. (2021). Adaptive Conformal Inference Under Distribution Shift. *NeurIPS 2021*. arXiv:2106.00170. **abstract + key equations**.
232. Barber, R. F., Candès, E. J., Ramdas, A., Tibshirani, R. J. (2023). Conformal prediction beyond exchangeability. *Annals of Statistics* 51(2). doi:10.1214/23-AOS2276 ; arXiv:2202.13415. **metadata**.
233. Ovadia, Y., Fertig, E., Ren, J., Nado, Z., Sculley, D., Nowozin, S., Dillon, J., Lakshminarayanan, B., Snoek, J. (2019). Can you trust your model's uncertainty? Evaluating predictive uncertainty under dataset shift. *NeurIPS 2019*. **abstract**.
234. Contreras, J. L., Shorinwa, O., Schwager, M. (2024). Safe, Out-of-Distribution-Adaptive MPC with Conformalized Neural Network Ensembles. arXiv:2406.02436. **abstract**.
235. Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review* 78(1):1-3. **background**.
236. Guo, C., Pleiss, G., Sun, Y., Weinberger, K. Q. (2017). On Calibration of Modern Neural Networks. *ICML 2017*, PMLR 70:1321-1330. arXiv:1706.04599. **abstract**.
237. Gneiting, T., Raftery, A. E. (2007). Strictly Proper Scoring Rules, Prediction, and Estimation. *JASA* 102(477):359-378. **metadata**.
238. Kuleshov, V., Fenner, N., Ermon, S. (2018). Accurate Uncertainties for Deep Learning Using Calibrated Regression. *ICML 2018*, PMLR 80:2796-2804. **metadata**.
239. Lakens, D. (2017). Equivalence Tests: A Practical Primer for t Tests, Correlations, and Meta-Analyses. *Social Psychological and Personality Science* 8(4):355-362. doi:10.1177/1948550617697177. **abstract**.
240. Schuirmann, D. J. (1987). A comparison of the two one-sided tests procedure and the power approach for assessing the equivalence of average bioavailability. *J. Pharmacokinetics and Biopharmaceutics* 15:657-680. **background** (used for the statistical method only).

## Area 9: Perturbation-based validation (methodology)

241. Sourmpis, C., Petersen, C., Gerstner, W., Bellec, G. (2025). Biologically informed cortical models predict optogenetic perturbations. *eLife*. doi:10.7554/eLife.106827 ; code https://github.com/Sourmpis/BiologicallyInformed. **full** (only methodological content used).
242. Das, A., Fiete, I. R. (2020). Systematic errors in connectivity inferred from activity in strongly recurrent networks. *Nature Neuroscience* 23:1286-1296. doi:10.1038/s41593-020-0699-2. **abstract**.
243. Galgali, A. R., Sahani, M., Mante, V. (2023). Residual dynamics resolves recurrent contributions to neural computation. *Nature Neuroscience* 26:326-338. doi:10.1038/s41593-022-01230-2 ; code https://github.com/anirgalgali/residual-dynamics (MIT). **abstract + code README**.
244. Qian, W., Zavatone-Veth, J. A., Ruben, B. S., Pehlevan, C. (2024). Partial observation can induce mechanistic mismatches in data-constrained models of neural dynamics. *NeurIPS 2024*. https://openreview.net/forum?id=LCEgP7Ir6k. **abstract** [author details unverified].
245. Schuessler, F., Mastrogiuseppe, F., Ostojic, S., Barak, O. (2024). Aligned and oblique dynamics in recurrent neural networks. *eLife* 13:RP93060. arXiv:2307.07654. **abstract**.
246. Jazayeri, M., Ostojic, S. (2021). Interpreting neural computations by examining intrinsic and embedding dimensionality of neural activity. *Current Opinion in Neurobiology* 70:113-120. arXiv:2107.04084. **abstract**.
247. Wan, Y., Rosenbaum, R. (2025/2026). High-dimensional dynamics in low-dimensional networks. arXiv:2504.13727 [journal version unverified]. **abstract**.
248. Otchy, T. M., Wolff, S. B. E., Rhee, J. Y., Pehlevan, C., Kawai, R., Kempf, A., Gobes, S. M. H., Ölveczky, B. P. (2015). Acute off-target effects of neural circuit manipulations. *Nature* 528:358-363. doi:10.1038/nature16442. **abstract** (only the methodological lesson used; author initials partly [unverified]).
249. Wolff, S. B. E., Ölveczky, B. P. (2018). The promise and perils of causal circuit manipulations. *Current Opinion in Neurobiology* 49:84-94. **abstract** [DOI unverified].
250. Jonas, E., Kording, K. P. (2017). Could a Neuroscientist Understand a Microprocessor? *PLOS Computational Biology* 13(1):e1005268. doi:10.1371/journal.pcbi.1005268. **full**.
251. Durstewitz, D., Koppe, G., Thurm, M. I. (2023). Reconstructing computational system dynamics from neural data with recurrent neural networks. *Nature Reviews Neuroscience* 24:693-710. doi:10.1038/s41583-023-00740-7. **abstract**.

## Area 10: Counterexample-guided refinement and falsification

252. Clarke, E., Grumberg, O., Jha, S., Lu, Y., Veith, H. (2000). Counterexample-Guided Abstraction Refinement. *CAV 2000*, LNCS 1855:154-169 ; journal: *J. ACM* 50(5):752-794 (2003). **abstract**.
253. Solar-Lezama, A. (2008). *Program Synthesis by Sketching*. PhD thesis, UC Berkeley. **metadata**.
254. Elboher, Y. Y., Gottschlich, J., Katz, G. (2020). An Abstraction-Based Framework for Neural Network Verification. *CAV 2020*, LNCS 12224:43-65. **abstract**.
255. Waga, M. (2020). Falsification of Cyber-Physical Systems with Robustness-Guided Black-Box Checking. *HSCC 2020*. arXiv:2005.02126. **abstract**.
256. Annpureddy, Y., Liu, C., Fainekos, G., Sankaranarayanan, S. (2011). S-TaLiRo: A Tool for Temporal Logic Falsification for Hybrid Systems. *TACAS 2011*, LNCS 6605:254-257. **abstract**.
257. Donzé, A. (2010). Breach, A Toolbox for Verification and Parameter Synthesis of Hybrid Systems. *CAV 2010*, LNCS 6174:167-170. **abstract**.
258. Dreossi, T., Fremont, D. J., Ghosh, S., Kim, E., Ravanbakhsh, H., Vazquez-Chanlatte, M., Seshia, S. A. (2019). VerifAI: A Toolkit for the Formal Design and Analysis of Artificial Intelligence-Based Systems. *CAV 2019*. arXiv:1902.04245. **abstract**.
259. Deshmukh, J., Horvat, M., Jin, X., Majumdar, R., Prabhu, V. S. (2017). Testing Cyber-Physical Systems through Bayesian Optimization. *ACM TECS* 16(5s). doi:10.1145/3126521. **metadata**.
260. Ramezani, Z., Šehić, K., Nardi, L., Åkesson, K. (2022/2025). Falsification of Cyber-Physical Systems using Bayesian Optimization. arXiv:2209.06735. **abstract**.
261. Corso, A., Moss, R. J., Koren, M., Lee, R., Kochenderfer, M. J. (2021). A Survey of Algorithms for Black-Box Safety Validation of Cyber-Physical Systems. *JAIR* 72:377-428. arXiv:2005.02979. **abstract**.
262. Pei, K., Cao, Y., Yang, J., Jana, S. (2017). DeepXplore: Automated Whitebox Testing of Deep Learning Systems. *SOSP 2017*. **abstract**.
263. Madry, A., Makelov, A., Schmidt, L., Tsipras, D., Vladu, A. (2018). Towards Deep Learning Models Resistant to Adversarial Attacks. *ICLR 2018*. arXiv:1706.06083. **background**.
264. Smith, R. S., Doyle, J. C. (1992). Model validation: a connection between robust control and identification. *IEEE TAC* 37(7):942-952. **abstract**.

---

**Count:** 264 numbered entries. Of these, 255 are papers, books or theses. The rest are software entries (dynamax, ssm,
PyDMD, PyKoopman, pysindy, nfoursid, SIPPY, PyPSID) and one grouped software line (entry 222). Entry 36 is `[unverified]`
bibliographically, and entries 8, 170, 171, 208, 235, 240 and 263 are **background** (not read in this session).

Additional works were mentioned in the notes but not read and are not cited as evidence: Cowan et al. 2012; Tassa et al.
2014; Makelov et al. 2024; Kemertas & Aumentado-Armstrong 2021; Banijamali et al. 2018; Morrill et al. 2021; Goda et al.
arXiv:2005.08414; arXiv:2501.16625; arXiv:1610.05561. Wherever the review refers to them, the claim is marked `[unverified]`.
