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

## Builder mode: retired (Zayd, 17 Oct 21:40)

Codex no longer writes code or runs cluster steps in this repository. Claude Code builds and runs. Codex reviews and commits only, as described above. The builder entries from 20:49 to 21:25 on 17 October stay in the chat as history.
