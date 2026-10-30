# AI declaration: relevant prompts (draft for Zayd's review, 30 Oct)

These are Zayd's own prompts to the AI tools, quoted as written. Only obvious typos are corrected, and `[...]` marks a cut. Tick the ones to keep (aim for 10–15), add the ChatGPT ones at the end, and Codex will lay them out as the page after the form.

**Context line for the page:** "AI tools were used under a fixed division of roles: an AI supervisor (ChatGPT, later Claude) proposed experiments and ruled on results in a written, append-only supervision log; Claude Code wrote and ran code and cluster jobs; Codex reviewed and committed changes. Every experiment, job submission and commit required my explicit approval. The full log is kept in the project repository. Representative prompts follow."

## 1. Project set-up and supervision (Claude)
- [ ] "I have an Honours in Computer Science Research Project that I need help with and supervising." *(project description)*
- [ ] "check chat" *(the standing instruction: read the newest supervision-log entries, verify the claims against the saved results and post a ruling)*

## 2. Experiment design and analysis (Claude)
- [ ] "The experiment deadline can be abolished [...] seeds [...] mean and std deviation [...] reproduction fault [...] statistically what's causing it" *(after the supervisor meeting; this led to the seed replication and the S3PL seed analysis)*
- [ ] "I do not want any incomplete stuff experiment wise and reasons to look incomplete so if we need to run anything more have us do that before writing the report please."
- [ ] "Also I do not like that we have empty in the msiPL for RCC can't we run something to fix that?"
- [ ] "bigbatch seems to be overloaded again so can we use batch or do we need bigbatch for these? also please make a decision tracker to track the decisions we make so we don't accidentally go back on them."
- [ ] "Also we are back to the 10 epochs vs 100 epochs thing. Why didn't we evaluate when the scores are no longer increasing and choose that as our epochs?" *(the AI advised against it: tuning on the label-based score would select on the evaluation labels)*

## 3. Code development and execution (Claude Code, via prompts Zayd sent)
- [ ] "You're the builder for the Spatial-msiPL MSI project. [...] Do items 1, 2, 3, 4 and 5 from that entry [...] For every sbatch, post a pre-submission checklist and wait for my explicit OK [...] Never overwrite, delete or --delete [...] Don't commit." *(session prompt, drafted with the supervisor's help)*
- [ ] "OK to submit the GPU array (ig 0-11)." *(an example of the per-job approval)*

## 4. Review and commits (Codex)
- [ ] "Check chat; review and commit gate v2 per the latest Supervisor ruling."
- [ ] "You're now allowed to edit the report text, not just review it [...]. Apply your v3 findings 1–4 [...]. Resolve the bibliography entries marked VERIFY [...] from primary sources [...]. Never invent a number."

## 5. Writing the report (Claude, Codex)
- [ ] "Ok make a draft for me please and then I will review it and kind of go through and see what I like and don't like and make corrections and then we can go from there."
- [ ] "Remove the proposal to outcome table, let's just have a paper in its current form [...]. Write it like any of the papers we read."
- [ ] "When I write anything I usually don't use a comma before 'and' because that's how I was taught in school. We used British English [...]"
- [ ] (Draft review) "Can we better phrase the helps, equivalent etc.? Maybe explain how we decide it and then use the connotations after. [...] Hairong also mentioned that she doesn't like seeing seed 1 seed 2 seed 3 so we need to change it up."

## 5b. Zayd's preferred categories (30 Oct): review, graphs, commits, cluster commands, documentation

**Review**
- [x] "check what me and codex did"
- [x] "Have a look because I asked Codex [...] give me the code prompt to [...] double check everything"
- [x] "Did we have a page limit? Hairong said the limit is 8 pages [...]" / "You did read the proposal to see what I said and how it was said there right?"

**Graphs and figures**
- [x] "Does figure 5 hold any significant meaning and really add that much to the report? [...] I would like the runtime graph, that is cool."
- [x] "Also dont we have the architecture in pdf form somewhere where I asked you to make them a while ago in latex?"
- [x] "Would we not want to include images of the actual dataset or is that not something this paper needs?"

**Commit messages and cluster commands**
- [x] "I may need you to just give me the commands and a very concise message instead [...]. You know that there are some stuff that I just don't want to have included in a commit message right, like the AI names or dates."
- [x] "bigbatch seems to be overloaded again so can we use batch or do we need bigbatch for these?"
- [x] "Why did we tie the rcc jobs to nodes [...] do we need exclusive nodes? [...] can we not run it all on batch?"

**Notion and documentation**
- [x] "Add the plan to the Notion and docs."
- [x] "Ok I'll just let it run through the night [...] make a note of everything [...] update the Notion."
- [x] "Change task 10 to exclude the report and then let's make a bunch of new tasks for the report."

## 6. ChatGPT (Zayd to add, from his ChatGPT history)
- [ ] ...
- [ ] ...
