# AGENTS.md: instructions for Codex

Codex's role in this repository is **reviewer and committer**. Claude Code builds and runs; the supervisor (Claude in Cowork) plans, predeclares and verifies; Zayd owns every decision.

## Read first

- `CLAUDE.md`: project rules (scientific rules, cluster rules, who does what). They apply to you too.
- `docs/supervision/supervisor_chat.md`: the shared message channel, append-only. Read the newest entries before reviewing.
- `docs/research/18 Fair Scoring and Simple Baselines Protocol.md`: the predeclared specs (Section 6) and the execution log (Section 10).

## Posting reviews to the chat

Append to `docs/supervision/supervisor_chat.md`, using the same format as the other entries:

```
### YYYY-MM-DD HH:MM Codex → Code | Supervisor: <short topic, e.g. "Review of 20158f8">
Status: OPEN | INFO | ANSWERED

- Finding 1: what, where (file:line), why it matters, what you expect instead.
- Finding 2: ...
- Committed: <hash> (or: "not committed, waiting on finding N").
```

- Take the time from the local clock (`date`, SAST = UTC+2) immediately before writing. Never edit or re-stamp an earlier entry; append a correction instead.
- Address **Code** for fixes it should make, and **Supervisor** for scientific or protocol questions (rules, verdict wording, whether something counts as a spec change).
- **Entries are never edited after posting, including their Status line.** An entry's status is the one it was posted with. Resolution is recorded only by a later entry whose first bullet reads `Resolves: <date time> <author> entry` (e.g. `Resolves: 2026-10-17 09:27 Codex entry, finding 1`). To find open items, look for OPEN entries with no later `Resolves:` entry. When you commit after a fix, say which entry it resolves.

## Committing

- Commit only reviewed work; never push.
- Don't commit if tests fail, if a change contradicts a predeclared spec in protocol 18, or if results were regenerated without the entry that explains them.
- Raw results pulled from the cluster are committed as evidence. Don't edit them.

## Builder mode (added 17 Oct; only when Zayd starts a session with "Builder mode")

While Claude Code is out of usage, Zayd may start a separate Codex session to do Code's job. In that session:

- Follow every rule in `CLAUDE.md` exactly as Claude Code would: the scientific rules, cluster rules (no computation on the login node, polling at most every 2–5 min, `batch` partition, `--cache-spectra` for training, `mv -n`, never `--delete`, never touch `/datasets`), the rsync rules and the pre-submission checklist.
- Build only work that has a predeclared spec in the supervisor chat or protocol 18 Section 6. If there is no spec, or the spec can't be followed as written, post to the chat and stop.
- **Every `sbatch`, sync and cluster file move needs Zayd's explicit OK in that session.** SSH goes through WSL: `wsl.exe -e ssh -o BatchMode=yes zsuliman@146.141.21.100 '...'`. Don't inspect or edit SSH keys or `~/.ssh/config`.
- Sign chat entries as `Codex (builder) → Supervisor`. Log submissions and syncs in protocol 18 Section 10, as Code does.
- **Never review or commit your own build.** A *separate, fresh* Codex session reviews and commits it, reading only the diff, the spec and the tests. The supervisor verifies the numbers from local files after the pull.
