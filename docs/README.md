# References: Scientific basis for Kaizen's evaluation methodology

Supporting material for the treatment/control, paired-statistical-test
evaluation design (see main `README.md` → "Risk tiers" / regression-safety
discussion). Where a paper is legitimately open-access (ACL Anthology,
NeurIPS open proceedings, or an author's own officially-hosted public copy),
the PDF is included in `docs/papers/`. Everything else is paywalled
(IEEE/Wiley/Springer/book) and is linked only, per copyright — no paywalled
content is redistributed here.

## Downloaded (open access)

| File | Citation | Relevance |
|---|---|---|
| `papers/dror-et-al-2018-hitchhikers-guide.pdf` | Dror, R., Baumer, G., Shlomov, S., & Reichart, R. (2018). *The Hitchhiker's Guide to Testing Statistical Significance in Natural Language Processing.* ACL. | Standard reference for using McNemar's test to compare two systems (baseline vs. candidate) on the same eval set. |
| `papers/ribeiro-et-al-2020-checklist.pdf` | Ribeiro, M. T., Wu, T., Guestrin, C., & Singh, S. (2020). *Beyond Accuracy: Behavioral Testing of NLP Models with CheckList.* ACL (Best Paper). | Precedent for splitting an eval set into tagged capability/category slices and checking for regressions per slice — the basis for our treatment/control split. |
| `papers/sculley-et-al-2015-hidden-technical-debt.pdf` | Sculley, D. et al. (2015). *Hidden Technical Debt in Machine Learning Systems.* NeurIPS. | Source of the "Changing Anything Changes Everything" (CACE) principle — the justification for why a control group is required when patching one behavior. |
| `papers/kohavi-et-al-2009-controlled-experiments.pdf` | Kohavi, R., Longbotham, R., Sommerfield, D., & Henne, R. M. (2009). *Controlled experiments on the web: survey and practical guide.* Data Mining and Knowledge Discovery, 18(1), 140–181. (Author-hosted copy via exp-platform.com) | Foundational treatment/control, A/B experimentation methodology. |

## Linked only (paywalled journal articles / books — not redistributable)

- McNemar, Q. (1947). *Note on the sampling error of the difference between correlated proportions or percentages.* Psychometrika, 12(2), 153–157. https://doi.org/10.1007/BF02295996 — origin of the statistical test itself.
- Dietterich, T. G. (1998). *Approximate statistical tests for comparing supervised classification learning algorithms.* Neural Computation, 10(7), 1895–1923. https://doi.org/10.1162/089976698300017197 — recommends McNemar's test over naive accuracy-diffs.
- Rothermel, G., & Harrold, M. J. (1996). *Analyzing regression test selection techniques.* IEEE Trans. Software Engineering, 22(8), 529–551. https://doi.org/10.1109/32.536955 — foundational test-impact-analysis paper (basis for tagging the "treatment" split).
- Yoo, S., & Harman, M. (2012). *Regression testing minimization, selection and prioritization: A survey.* Software Testing, Verification and Reliability, 22(2), 67–120. https://doi.org/10.1002/stvr.430 — survey establishing this as a mature subfield.
- Cochran, W. G. (1977). *Sampling Techniques* (3rd ed.). Wiley. ISBN 978-0471162407 — standard textbook reference for stratified sampling design (basis for the control-split sampler).
- Anthropic Engineering (2025). *How we built our multi-agent research system.* https://www.anthropic.com/engineering/multi-agent-research-system — the original inspiration for Kaizen's Runner/Fixer design and "let agents improve themselves" framing.
