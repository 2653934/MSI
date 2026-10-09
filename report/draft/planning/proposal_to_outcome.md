# Proposal-to-outcome account

Status: working source for the final report, 9 October 2026.

This table records what changed from the approved proposal and why. A changed
method is not concealed as if it had been proposed from the start, and a
negative pilot is not generalised beyond what it tested.

| Proposal commitment | Evaluated outcome | Status | Reasoning and report consequence |
|---|---|---|---|
| Concatenate each central spectrum with the mean of its immediate Moore neighbourhood and reconstruct the centre. | Implemented centre-only and contextual VAEs; evaluated fixed 3×3 means, 5×5 means, zero/shuffled controls and learned attention. | Delivered and extended. | This became the main controlled investigation. The report must distinguish context-versus-centre from real-versus-shuffled topology. |
| Add an explicit spatial-coherence penalty to the VAE objective. | Bounded penalty pilots were run but the penalty was not retained in the principal model. | Tested but not retained. | The pilots do not prove that every formulation or strength of spatial regularisation is ineffective. The final report must state the tested range and avoid a universal negative claim. |
| Inject Poisson noise as a physical prior during training. | Poisson augmentation was calibrated and tested in development pilots but was not retained. | Tested but not retained. | Separate penalty and augmentation pilots do not answer whether their interaction could help. The combined intervention remains an unanswered proposal question and future-work item. |
| Use Bayesian optimisation to select the spatial-penalty coefficient. | The study used bounded, discrete penalty pilots instead. | Methodological change. | Bayesian optimisation is omitted because the penalty was not promoted after the bounded development evidence. The report cannot claim that the penalty was globally optimised or cannot work. |
| Derive peaks using backpropagated first-layer weight analysis. | First-layer L2 was retained as a comparator. The principal new ranking fits a label-free two-component GMM to frozen latent means and applies Integrated Gradients to its posterior. | Replaced and retained as comparator. | First-layer L2 performed poorly as an explanation of the nonlinear pipeline. GMM-targeted IG was introduced to attribute the complete encoder and a biologically unlabelled latent-separation target. The report must not attribute the entire improvement to IG alone because architecture, training and selection also differ from legacy msiPL. |
| Benchmark against msiPL, S3PL and MALDIquant. | Legacy msiPL and executable S3PL were reproduced and extensively audited. MALDIquant was not completed. | Partly delivered; MALDIquant omitted. | The report may compare against the evaluated learning-based baselines. It must not claim superiority over classical peak picking in general. MALDIquant is deferred rather than rushed because it does not change the central neighbourhood-context question. |
| Use raw profile-mode GBM and CAC MSI data. | Public GBM/CAC representations and audited adapters were used, including imzML-to-HDF5 preparation where required. | Delivered with provenance limits. | HDF5 versus imzML format alone does not prove full profile-mode fidelity. The report must describe upstream provenance, normalisation, coordinate/mask alignment and what the bounded audits did not verify. |
| Improve biologically relevant peak discovery. | The VAE/GMM/IG package improves matched-budget mSCF1 over reproduced legacy msiPL on both collections. Spatial-context gains are collection-dependent, and S3PL remains stronger on matched-count CAC. | Partly supported with narrower interpretation. | mSCF1 measures agreement between selected-bin ion images and expert masks. It does not identify molecules, establish biomarkers or prove that non-correlated bins are noise. |
| Provide a computationally efficient alternative to 3D convolution. | Three native 160TopL workflow measurements found VAE totals of 121.6--135.3 s versus S3PL totals of 151.2--173.9 s, with slightly lower sampled memory for the VAE stages. Protocols used 100 and 10 epochs respectively. | Supported only as a bounded native-workflow observation. | Report wall time, CPU time, RSS and sampled GPU memory with timer boundaries. Do not describe this as an equal-work or universal architectural-efficiency result. |
| Establish that local spatial context improves peak selection. | Uniform context improves the frozen single-seed CAC comparison but not GBM; real/shuffled and learned-attention controls do not establish a consistent benefit specifically attributable to correct local topology across both collections. | Mixed/negative central finding. | This is a valid research result. The report must preserve the positive CAC comparison while explaining why later controls weaken a general causal spatial claim. |

## Decision on MALDIquant

MALDIquant will not be added merely to reproduce every proposed activity. Its
omission is acceptable only with the following restriction:

> The evaluated VAE/GMM/Integrated-Gradients pipeline is compared with the
> reproduced learning-based msiPL and S3PL baselines; this study does not
> establish superiority over classical peak-picking methods in general.

If Hairong or the assessment requirements explicitly require a classical
baseline, this decision must be revisited before submission.

