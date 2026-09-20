# Cluster sync commands

These commands map the local executable workspace to the cluster workspace:

```text
Local:   C:\Users\zayds\Documents\Research\MSI\code\msi\
Cluster: /home-mscluster/zsuliman/msi/
```

Run the local commands from `code/msi`, **not** from the outer `MSI`
repository. The trailing slashes are intentional: they copy the contents of
one workspace into the other workspace.

## Before every transfer

In Git Bash, first move to the correct local directory and check it:

```bash
cd /c/Users/zayds/Documents/Research/MSI/code/msi
test -d slurm_jobs -a -d scripts -a -d results || {
  echo "Wrong directory: expected the local code/msi workspace"
  exit 1
}
pwd
```

If using WSL, the equivalent path normally starts with
`/mnt/c/Users/zayds/...`.

## Recommended: collect only cluster artifacts

This is the safest normal download. It brings back results, logs and
reproducibility records without replacing local source code.

Preview the result transfer:

```bash
rsync -avzn --itemize-changes \
  --exclude='__pycache__/' \
  --exclude='*.py[cod]' \
  --exclude='*.pt' \
  --exclude='*.pth' \
  --exclude='*.ckpt' \
  zsuliman@146.141.21.100:/home-mscluster/zsuliman/msi/results/ \
  ./results/
```

Collect all three artifact directories:

```bash
rsync -avz --progress \
  --exclude='__pycache__/' \
  --exclude='*.py[cod]' \
  --exclude='*.pt' \
  --exclude='*.pth' \
  --exclude='*.ckpt' \
  zsuliman@146.141.21.100:/home-mscluster/zsuliman/msi/results/ \
  ./results/

rsync -avz --progress \
  --exclude='__pycache__/' \
  --exclude='*.py[cod]' \
  zsuliman@146.141.21.100:/home-mscluster/zsuliman/msi/logs/ \
  ./logs/

rsync -avz --progress \
  --exclude='__pycache__/' \
  --exclude='*.py[cod]' \
  --exclude='*.pt' \
  --exclude='*.pth' \
  --exclude='*.ckpt' \
  zsuliman@146.141.21.100:/home-mscluster/zsuliman/msi/reproducibility/ \
  ./reproducibility/
```

These commands do not use `--delete`. A locally deleted file can therefore
reappear if it still exists on the cluster. That is deliberate protection
against accidentally deleting cluster evidence. Remove confirmed obsolete
paths on both sides only after current jobs have finished.

## Upload source changes to the cluster

Use this when the local workspace contains the source changes that a cluster
job needs. It deliberately does not upload local results, logs or
reproducibility artifacts over the cluster copies.

Preview first:

```bash
rsync -avzn --itemize-changes \
  --exclude='.git/' \
  --exclude='data/' \
  --exclude='checkpoints/' \
  --exclude='weights/' \
  --exclude='results/' \
  --exclude='logs/' \
  --exclude='reproducibility/' \
  --exclude='__pycache__/' \
  --exclude='*.py[cod]' \
  --exclude='*.pt' \
  --exclude='*.pth' \
  --exclude='*.ckpt' \
  --exclude='*.h5' \
  --exclude='*.imzML' \
  --exclude='*.ibd' \
  --exclude='*.zip' \
  --exclude='*.7z' \
  ./ \
  zsuliman@146.141.21.100:/home-mscluster/zsuliman/msi/
```

Then perform the upload by changing `-avzn` to `-avz`:

```bash
rsync -avz --progress \
  --exclude='.git/' \
  --exclude='data/' \
  --exclude='checkpoints/' \
  --exclude='weights/' \
  --exclude='results/' \
  --exclude='logs/' \
  --exclude='reproducibility/' \
  --exclude='__pycache__/' \
  --exclude='*.py[cod]' \
  --exclude='*.pt' \
  --exclude='*.pth' \
  --exclude='*.ckpt' \
  --exclude='*.h5' \
  --exclude='*.imzML' \
  --exclude='*.ibd' \
  --exclude='*.zip' \
  --exclude='*.7z' \
  ./ \
  zsuliman@146.141.21.100:/home-mscluster/zsuliman/msi/
```

Why `.git/` matters: the imported `baselines/msipl` directory still contains
its original upstream Git metadata. Sending that metadata adds clutter and can
make Git commands act on the wrong repository. The remote workspace may also
have its own `.git` directory, which should never be copied back into
`code/msi`.

## Full cluster-to-local recovery pull

Use this only when source files were intentionally edited on the cluster and
must be recovered. The targeted artifact pull above is safer for daily work.

Preview:

```bash
rsync -avzn --itemize-changes \
  --exclude='.git/' \
  --exclude='data/' \
  --exclude='checkpoints/' \
  --exclude='weights/' \
  --exclude='__pycache__/' \
  --exclude='*.py[cod]' \
  --exclude='*.pt' \
  --exclude='*.pth' \
  --exclude='*.ckpt' \
  --exclude='*.h5' \
  --exclude='*.imzML' \
  --exclude='*.ibd' \
  --exclude='*.zip' \
  --exclude='*.7z' \
  zsuliman@146.141.21.100:/home-mscluster/zsuliman/msi/ \
  ./
```

Perform the full pull only after checking that preview:

```bash
rsync -avz --progress \
  --exclude='.git/' \
  --exclude='data/' \
  --exclude='checkpoints/' \
  --exclude='weights/' \
  --exclude='__pycache__/' \
  --exclude='*.py[cod]' \
  --exclude='*.pt' \
  --exclude='*.pth' \
  --exclude='*.ckpt' \
  --exclude='*.h5' \
  --exclude='*.imzML' \
  --exclude='*.ibd' \
  --exclude='*.zip' \
  --exclude='*.7z' \
  zsuliman@146.141.21.100:/home-mscluster/zsuliman/msi/ \
  ./
```

## What was corrected from the old commands

- `.git/` is excluded in both directions.
- The malformed `*.pt`/`*.pth` portion of the pasted download command is
  repaired.
- Python bytecode uses valid patterns: `__pycache__/` and `*.py[cod]`.
- Uploads do not overwrite cluster-generated results or logs.
- Daily downloads target artifacts instead of overwriting the whole local
  source tree.
- Every risky transfer has a dry-run form using `-n --itemize-changes`.

Do not add `--delete` casually. It turns a copy command into a mirror operation
and can remove files on the destination.
