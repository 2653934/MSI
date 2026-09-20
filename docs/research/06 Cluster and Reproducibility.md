# Cluster and Reproducibility

## Canonical locations

```text
Repository:  /home-mscluster/zsuliman/msi/
Raw data:    /datasets/zsuliman/msi_data/
Checkpoints: /datasets/zsuliman/msi_checkpoints/
```

Raw datasets and checkpoints should not be pulled into the local Git working
tree. They are large, reproducible from source data or unsafe to version in the
main repository.

## Environments

- `s3pl_env`: PyTorch, S3PL and Spatial-msiPL work.
- `data_tools_env`: data inspection/extraction tasks where appropriate.
- Legacy msiPL has older TensorFlow/Keras constraints and should not casually be
  merged into the PyTorch environment.

Conda activation can be slow on the network filesystem because it reads many
small files and runs activation hooks. A slow activation is not itself evidence
that training has started.

## Slurm lifecycle

Important states:

- `PD`: pending; inspect the reason such as Priority, Resources or Dependency.
- `R`: running.
- `CG`: completing; Slurm is cleaning up processes and node state.
- completed/failed jobs disappear from `squeue` but remain in `sacct`.

Authoritative timing command:

```bash
sacct -j JOB_ID -X \
  --format=JobID,State,Submit,Eligible,Start,End,Elapsed,NodeList,Restarts,ExitCode
```

`Submit` is when the job entered Slurm. `Start` is when computation actually
began. Queue waiting time must not be reported as model runtime.

## Logs

Slurm writes:

```text
logs/<job-name>-<job-id>.out
logs/<job-name>-<job-id>.err
```

Progress output is flushed so it can be monitored during a run. An `.err` file
is not automatically a failed job: test runners and warnings often write to
stderr. Always inspect `sacct`, exit code and expected result artifacts.

## Checkpoints and restartability

Production training saves:

- model parameters;
- optimiser state;
- learning-rate scheduler state;
- completed epoch and history;
- data-loader generator state;
- CPU and CUDA random states;
- Poisson generator state when used;
- configuration and resume signature.

Checkpoints are written atomically. A continuation verifies the resume signature
before training, preventing accidental resume with a different dataset, model
or hyperparameter configuration.

## CUDA preflight and adaptive failover

The cluster does not advertise a usable GPU GRES that our jobs can request.
Some nodes have intermittently exposed zero CUDA devices even though the same
environment works elsewhere.

The current attribution job therefore performs a real warm-up:

1. check `torch.cuda.is_available()`;
2. allocate GPU tensors;
3. perform matrix multiplication;
4. read a result and synchronise.

If this fails, the job records the node in:

```text
logs/gbm-ig-JOB_ID.failed_nodes
```

Slurm does not allow a running job to update its own exclusion list. The job
therefore submits a bounded replacement and, during a multi-section campaign,
repoints that dataset’s gate job so the final summary still waits for the
latest attempt.

Three consecutive September 20 canary attempts repeated historical failures on
`mscluster65`, `mscluster57` and `mscluster45`. Production GPU submissions now
start with the evidence-based quarantine in
`slurm_jobs/gpu_cuda_quarantine.txt`, then add any newly failing node to only
that retry chain. Historical evidence remains in
[cluster_node_issues.txt](../../code/msi/cluster_node_issues.txt). Quarantine is
not a declaration that hardware is permanently broken; removal should follow a
separate successful GPU health test rather than an expensive production job.

## Synchronisation

A typical result pull excludes raw data and checkpoints:

```bash
rsync -avz --progress \
  --exclude='data' \
  --exclude='checkpoints' \
  zsuliman@146.141.21.100:/home-mscluster/zsuliman/msi/ ./
```

This command does not delete files that still exist on the cluster. If a file
was removed locally but remains remotely, a later pull can restore it. Cleanup
must therefore be performed deliberately on the correct side, never with broad
recursive deletion against an unresolved path.

## What belongs in Git

Commit:

- source and Slurm scripts;
- compact JSON/CSV summaries;
- figures used for interpretation;
- relevant stdout/stderr evidence;
- manifests and documentation.

Do not commit:

- raw `.h5`, `.imzML`, `.ibd` or archives;
- conda environments and caches;
- `.pt`, `.pth` or other production checkpoints;
- temporary extraction directories.

## Reproducibility rules

1. Record dataset, seed, model variant and hyperparameters.
2. Preserve the exact evaluation protocol and matched peak budget.
3. Never silently overwrite a final checkpoint or result.
4. Separate development-section decisions from validation results.
5. Keep failed infrastructure attempts distinguishable from scientific failures.
6. Interpret JSON summaries from the code that produced them; do not manually
   recalculate only favourable sections.
