# Curation proposal (supervisor, 24 Oct). Zayd: change anything you disagree with

**Key:** **B** = body · **b** = body, brief (a sentence or two, or a table row) · **A** = appendix · **X** = cut. Item IDs refer to the dump files.
**Priorities from the marking weights:** Results 6, Methodology 3, Presentation 3. So keep the body focused, with strong tables and figures, and push detail to the appendix.

## Ch 1 Introduction
- **B:** C141–C146.

## Ch 2 Background and related work
- **B:**
  - C147 msiPL, C148 S3PL, C150 massNet (GBM source), C151 IG, C152 VAE, C153 and C154 (Alexandrov);
  - C156 Cardinal (RCC workflow), C157 Moran, C158 Alexandrov & Bartels, C160 Cassese;
  - C168 Mazarura, Jarvis & Bau, C172 Vaswani (attention), C173–C175 (MSI overview), C180 Deininger (normalisation);
  - C181 MALDIquant (classical peak picking), C186 Inglese (VAE for MSI), C187 DeepION, C190 Dill (RCC data).
- **b:** C149 IonMorphNet, C155, C159, C161, C185 M²aia; C162–C166 (graph and spatial-omics models, one paragraph, also used in future work).
- **Decide while writing:** C176–C178, C182–C184. Keep them only if they support a specific sentence.
- **X:** C167 (authors unverified), C179 (non-academic primer), C188 and C189 (tandem MS, off-topic).
- **Methods citations only:** C169 Schwarz (BIC), C170 scikit-learn; C171 only if ARI is reported.

## Ch 3 Research questions and proposal-to-outcome
- **B:** C191–C194.
- **B, as one table:** C195–C202 together with C213 (the proposal-to-outcome table).

## Ch 4 Methodology
- **Data, B:** C001–C006, C008, C009.
- **Data, b:** C234 (unverified CAC citation, as a footnote).
- **Data, A:** C221, C222.
- **Data, X:** C007 (superseded).
- **Models and evaluation, B:** C010–C020, C225 (exact IG definition), C226 (exact mSCF1 reference rule).
- **Models and evaluation, A:** C227.
- **Design and statistics, B:** C021–C029.
- **Design and statistics, b:**
  - C030 (Mann–Whitney: why it isn't the right test for paired data, and why it is "not done");
  - C215 (the predeclaration and append-only record, as part of the design).
- **Computational considerations (Hairong's request), B:** C031, C033, C035, C036.
- **Computational considerations, b:** C032, C034.
- **Computational considerations, A:** C037, C038.

## Ch 5 Results (6 points: the core)
1. **Reproductions:**
   - **B:** C039–C042, C080.
   - **b:** C043.
2. **Main ranking result:**
   - **B:** C044–C048, C050.
   - **b:** C049.
3. **Simple baselines and metric:**
   - **B:** C051, C053.
   - **b:** C052, C054.
4. **Spatial context:**
   - **B:** C055–C058, C063.
   - **b:** C059, C060.
   - **A:** C061, C062, C236–C238.
5. **Encoder and segmentation:**
   - **B:** C064–C067.
   - **A:** C068, C223, C224.
6. **S3PL:**
   - **B:** C069, C071, C072, C074–C077.
   - **b:** C073.
   - **A:** C070.
7. **RCC:**
   - **B:** C078, C079, C082.
   - **b:** C081.
   - **A:** C083.
   - (Alternatively, fold RCC into sections 1–2 rather than giving it its own section. Decide while writing.)
8. **Runtime:** covered in Ch 4 with C033 and C035. Results gives one line, pointing back.

## Ch 6 Discussion
- **B:** C084–C094, C228. The objection items C090–C094 map onto the scheme's "objections and responses".
- **b, used as a short "what we do not claim" paragraph:** C095–C100.
- **b, negative results named in the discussion:** C104 and C105.

## Ch 7 Conclusion and future work
- **B:** C203–C208.

## Appendices
- **A:** C209–C212, C214, C106 (the not-done list), C229.
- **Report back matter:** C218 and C235 (the AI declaration, required); C219 (code availability, body or back matter).
- **A:** C216, C217, C220.
- **X:** C101, C102, C103, C230 (superseded; they survive in the repository record).

## Figures and tables
- **Body figures (about 10):**
  - C111 fair-scoring methods;
  - C112 IG minus correlation by section;
  - C127 reproductions;
  - C115 GBM context by PDX line;
  - C124 all neighbourhood variants;
  - C130 VAE vs PCA;
  - C129 segmentation accuracy vs score;
  - C131 S3PL real vs shuffled;
  - C107 cache before/after;
  - **NEW: an Investigation 21 figure** (10-seed distributions per section with the published values marked; Code builds it from `part_b`/`part_a_released`).
  - Optional: C231 architecture diagram, if it can be updated to the final pipeline (a pipeline diagram helps Methodology).
- **Body tables:** C138 (the proposed primary tables), C137 (Section 6.6 F1/F2 plus a summary of the families), a Test R mean ± SD table, the runtime table (C134 subset), and the proposal-to-outcome table.
- **Appendix:** C108–C110, C113, C114, C116–C121, C123, C125, C126, C128, C132–C136, C139, C140, C232.
- **X:** C233 (historical).
- **Rebuild rule:** any figure or table showing per-seed values switches to mean ± SD (19 Oct rule). C121 and C115 need checking.
