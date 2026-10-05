# Cluster sync commands

In this project, "I synced" means a **cluster-to-local** download unless a
direction is explicitly stated. Uploading new source code is a separate step.

These commands map the local executable workspace to the cluster workspace:

```text
Local:   C:\Users\zayds\Documents\Research\MSI\code\msi\
Cluster: /home-mscluster/zsuliman/msi/
```

Run the local commands from `code/msi`, **not** from the outer `MSI`
repository. The trailing slashes are intentional: they copy the contents of
one workspace into the other workspace.

The curated visual gallery is at the outer repository's `results/` folder.
Because this folder is outside `code/msi`, none of the commands below upload
it. Cluster-generated results remain in `code/msi/results/`. If you ever
write a new upload command that starts from the outer `MSI` root, add
`--exclude='/results/'` to keep the gallery local.

`data` is a symbolic link rather than a physical directory in the workspace.
Its rsync rule is therefore `--exclude='/data'` without a trailing slash. This
matches the root entry itself whether it is a symlink, file or directory.

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

## Recommended: one quiet cluster-to-local artifact pull

Use this for ordinary downloads. It takes one SSH connection and brings back
only `results/`, `logs/` and `reproducibility/`; it cannot replace local source
code. It preserves file modification times for efficient incremental copies,
but not directory times, Unix ownership or permissions, which create noisy
metadata updates on the Windows-backed local folder. The exclude rules precede
the includes deliberately, so large binary artifacts stay on the cluster.

From the local `code/msi` directory, preview by adding `-n --itemize-changes`
after `rsync`, then run the same command without those preview options:

```bash
rsync -azO --no-perms --no-owner --no-group --info=name1,stats1 \
  --exclude='.git/' \
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
  --include='/results/***' \
  --include='/logs/***' \
  --include='/reproducibility/***' \
  --exclude='*' \
  zsuliman@146.141.21.100:/home-mscluster/zsuliman/msi/ \
  ./
```

There is no `--delete`: locally removed files can still reappear if they remain
on the cluster. That is deliberate protection against losing research evidence.

Remove confirmed obsolete paths on both sides only after current jobs have
finished.

## Upload source changes to the cluster

Use this when the local workspace contains the source changes that a cluster
job needs. It deliberately does not upload local results, logs or
reproducibility artifacts over the cluster copies.

Preview first:

```bash
rsync -avzn --itemize-changes \
  --exclude='.git/' \
  --exclude='/data' \
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
  --exclude='/data' \
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
  --exclude='/data' \
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
  --exclude='/data' \
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
- The `data` symlink is excluded as an entry, not mistaken for a directory.
- The malformed `*.pt`/`*.pth` portion of the pasted download command is
  repaired.
- Python bytecode uses valid patterns: `__pycache__/` and `*.py[cod]`.
- Uploads do not overwrite cluster-generated results or logs.
- Daily downloads target artifacts instead of overwriting the whole local
  source tree.
- Every risky transfer has a dry-run form using `-n --itemize-changes`.

Do not add `--delete` casually. It turns a copy command into a mirror operation
and can remove files on the destination.
