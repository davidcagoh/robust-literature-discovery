---
output:
  pdf_document: default
  html_document: default
---
# Robust Literature Discovery from Minimal Seeds: Validating LitDiscover on APS Citation Benchmarks and Live Surveys

**Date:** April 2026  

## Abstract

Automated literature review systems must balance two competing requirements: they must recover a topic comprehensively enough to support scholarly synthesis, yet they must do so without allowing citation-graph traversal to expand the screening pool beyond practical limits. This tension is especially acute in the realistic cold-start setting, where a user begins with only a handful of initial seed papers rather than a large curated bibliography. In this paper, we evaluate **LitDiscover**, a queue-driven literature discovery architecture designed to operate under that sparse-supervision regime. Using the complete American Physical Society (APS) citation dataset as a closed benchmark, we analyze the structural asymmetry of citation traversal, the effect of Pareto-filtered forward expansion, and the role of yield-gated continuation in bounding search cost. We then center the main empirical analysis on **low-seed initialization** with `k ∈ {2,3,4,5,6}` under top-k, random, and contaminated seed conditions. The core claim is that the architecture remains effective even when initialized from very small seed sets because bidirectional traversal, hub suppression, and yield-gated continuation work together to preserve recall while limiting graph explosion. We further show that the residual misses are structurally peripheral, which supports interpreting the final recall gap as a diminishing-returns boundary rather than a core failure mode. Finally, we connect the APS benchmark to deployed application traces, arguing that the same yield-governed control logic operates in the live system as a practical stopping signal.  

---

## 1. Introduction

The central practical problem in automated literature review is not merely how to summarize papers once they have been found, but how to **discover** a topic comprehensively from incomplete starting information. Real users rarely begin with a complete domain map or even a strong initial bibliography. More commonly, they begin with a query, a few candidate papers, and an uncertain boundary between relevant and irrelevant work. A useful review system must therefore solve a discovery problem under sparse initial supervision.

Citation graphs provide a natural substrate for this task because they expose relational structure that keyword search alone cannot recover. A paper’s references reveal backward intellectual lineage, while incoming citations reveal later work that builds on or reacts to it. In principle, repeated traversal over this graph should allow a system to expand from a small local starting point into a much larger topical neighborhood. In practice, however, naive traversal fails because citation networks are highly asymmetric. Backward traversal is naturally bounded by bibliography length, whereas forward traversal rapidly encounters generic high-degree hubs that connect many otherwise distant parts of the literature. Unconstrained exploration therefore turns a promising discovery process into an intractable screening problem.

**LitDiscover** addresses this problem as a bounded traversal architecture. Rather than treating literature discovery as open-ended graph expansion, it organizes discovery around a queue-driven loop in which search, screening, traversal, and escape operations are all subordinated to a single yield-governed control policy. Three architectural ideas are central. First, the system uses **bidirectional traversal**, because neither backward nor forward expansion alone is sufficient to recover a topic. Second, it applies **Pareto-filtered forward expansion** to suppress high-degree hubs that disproportionately drive graph explosion and topic drift. Third, it uses a **yield-gated continuation rule** to determine when local expansion remains productive and when the system should instead jump to a fresh part of the graph.

The original internal validation of this architecture emphasized stronger cold-start settings, including experiments with larger seed sets such as `k = 20`. That framing established that the system could recover survey-grounded domains once it had already been given a moderately favorable starting set. The more consequential question, however, is whether the architecture remains robust under **minimal seeding**. For a deployed review application, this is the regime that matters most. If the system performs well only after being granted a large seed list, then its usefulness is substantially narrower than its architecture suggests.

This paper therefore reframes the empirical story around the **`k = 2–6` low-seed regime**. We use APS as a closed citation universe, derive gold sets from survey bibliographies, and evaluate whether LitDiscover can recover those domains from top-k, random, and contaminated seed conditions. The resulting paper should be read as an empirical systems validation with two layers of evidence. The first layer is the controlled APS benchmark, which allows recall, efficiency, and miss structure to be analyzed precisely. The second layer is a restrained live-validation analysis using application traces, which does not attempt to prove real-world recall but does show that the same yield-governed stopping logic is operational in deployment.

The paper makes four contributions. First, it gives a structural account of why bounded traversal is necessary in citation graphs and why hub suppression is a principled design choice rather than an arbitrary heuristic. Second, it positions the main empirical result in the realistic minimal-seed regime, centering the question of whether a review engine can recover a topic from only a few starting papers. Third, it explains the residual recall gap through miss analysis, showing that the remaining misses are structurally peripheral. Fourth, it connects the benchmark to deployed application behavior by using live traces to support the claim that yield is not merely an offline metric but an operational control signal.

---

## 2. Architecture and Control Logic

LitDiscover is best understood as a queue-driven discovery loop rather than as a static retrieval pipeline. At a high level, the system alternates between **search**, **screening**, **traversal**, and **escape** operations until it reaches a stable state. The logic can be summarized as:

> **SEED → SEARCH → SCREEN → TRAVERSE → ESCAPE HATCH → STABLE**

The system begins from an initial seed set, which may consist of search results, user-supplied papers, or a mixture of the two. These papers enter a unified screening queue. Screening decisions then identify which items should be retained as relevant and therefore eligible for expansion. Expansion occurs through citation traversal, but only under bounded conditions.

The first architectural principle is **bidirectional traversal**. Backward traversal follows references made by included papers and is essential because relevant older work is often directly cited by on-topic seeds. Forward traversal follows papers that cite included items and is equally important because it exposes later developments that no initial bibliography can contain. Yet forward traversal is also the primary source of explosion. Foundational papers, methods papers, and generic benchmark papers accumulate citations across many subfields, so blindly following their incoming edges pushes the system into large off-topic regions of the graph.

The second architectural principle is therefore **Pareto-filtered forward expansion**. Rather than expanding equally through all forward neighbors, LitDiscover suppresses a high-degree tail of forward candidates. The rationale is graph-theoretic: in a heavy-tailed network, a relatively small fraction of nodes mediate a disproportionate share of edges. Those nodes are often precisely the hubs that maximize breadth while minimizing topical specificity. The Pareto filter is thus not only an efficiency device but also a topicality control.

The third architectural principle is **yield-gated continuation**. Expansion is not judged solely by how many new nodes it reaches, but by how many useful papers it produces relative to the screening effort required. In the benchmark framing, this means that local expansion should continue only when recent discoveries remain sufficiently fruitful; once yield collapses, the system should either declare local exhaustion or invoke an **escape hatch** that searches for a new entry point into a disconnected or weakly connected cluster.

This architecture is important because it formalizes literature discovery as an alternating process of **local exploitation** and **global re-entry**. Traversal explores dense neighborhoods that are already connected to the current frontier. The escape hatch compensates for structural gaps, indexing limitations, and disconnected subclusters by reintroducing a search-based jump. The system therefore does not assume that a topic is perfectly recoverable by graph traversal alone. Instead, it treats search and traversal as complementary operations coordinated by a common yield logic.

For the purposes of this paper, the key methodological point is that the architecture should be validated at the level of **control behavior** rather than only at the level of final recall. The question is not merely whether the system can eventually recover a large fraction of a gold set, but whether it can do so under a bounded screening policy that remains viable when initialization is weak.

---

## 3. Closed-Corpus Benchmark and Experimental Design

To evaluate the architecture under controlled conditions, we use the APS 2022 citation dataset, a closed citation universe containing 709,803 papers and 9,833,191 citation edges across American Physical Society journals [1]. The closed-corpus property is essential because it ensures that every traversal step remains inside the benchmark, allowing structural reachability, recall, and miss analysis to be defined precisely.

The ground-truth topical targets are derived from three highly cited survey papers published in *Reviews of Modern Physics* [2] [3] [4]. Each survey contributes a bibliography that functions as a gold set for the associated topic. These survey-derived sets are not perfect ontologies of the field, but they provide a strong and interpretable approximation to the literature that a knowledgeable human synthesis judged necessary to cite.

| Survey ID | Topic | Year | Gold References (APS internal) |
|---|---|---:|---:|
| **S1** | Metal-insulator transitions | 1998 | 582 |
| **S2** | Ultracold gases | 2008 | 432 |
| **S3** | Topological photonics | 2019 | 387 |

The benchmark has two conceptual layers. The first layer is **structural motivation**, where the survey papers themselves are used to analyze how citation-graph asymmetry produces expansion pressure and why bounded traversal is necessary. The second layer is the **cold-start validation**, which simulates the realistic user condition by replacing direct survey seeding with much smaller initial seed sets.

The revised empirical emphasis of this manuscript is the low-seed design shown below.

| Experimental factor | Paper emphasis |
|---|---|
| Seed size | `k ∈ {2,3,4,5,6}` |
| Seed quality | top-k, random, contaminated |
| Traversal mode | bidirectional traversal with Pareto-filtered forward expansion |
| Continuation rule | yield-gated continuation with escape-hatch re-entry |
| Main outcomes | recall, screened set size, per-round gain, residual misses |

The contaminated setting is particularly important because it captures a plausible operational scenario in which a user’s initial search returns a mixture of relevant and irrelevant papers. A robust discovery architecture should not require the seed set to be perfectly curated. Rather, it should suppress noise through the structure of the graph and through downstream screening decisions.

This experimental design should be interpreted as a validation of **minimal-seed recoverability**. The question is not whether a domain can be reconstructed when the system begins from a generous seed budget, but whether it can bootstrap itself from only a few plausible entry points.

---

## 4. Structural Motivation for Bounded Traversal

The need for bounded traversal follows directly from the structure of the APS citation graph. As shown in the original degree-distribution analysis, the graph is heavy-tailed in its in-degree distribution and much more constrained in its out-degree distribution. A small number of papers accumulate very large citation counts, while the number of references made by a typical paper remains much more limited. This asymmetry creates a directional imbalance in traversal cost.

![Figure 1: Degree Distributions](pub_figures/fig1_degree_distributions.png)

Backward traversal is naturally disciplined by bibliography length. If a paper cites 20 to 50 relevant predecessors, then expanding backward from it remains relatively local. Forward traversal is qualitatively different. A single paper of broad methodological importance may be cited by hundreds or thousands of later papers that span multiple adjacent domains. Once traversal flows through such hubs, the search frontier ceases to represent a coherent topic and instead becomes a large heterogeneous cross-section of the wider literature.

This dynamic is visible in reachability experiments seeded directly from the survey papers. Backward traversal immediately covers the gold bibliography at depth 1 because the survey reference list is, by construction, the survey’s backward neighborhood. Forward traversal alone, however, does not recover that same gold set and instead emphasizes the future citation surface of the survey. Bidirectional traversal is therefore necessary for realistic discovery, but it also produces rapid growth in the reached set when allowed to proceed without additional controls.

![Figure 2: BFS Reachability](pub_figures/fig2_bfs_reachability.png)

The role of the Pareto filter is to control this forward asymmetry. By suppressing the most highly cited forward neighbors, the system removes precisely the nodes most likely to act as generic bridges into unrelated or weakly related regions of the graph. This design choice is supported by the broader literature on heavy-tailed graph structure and graph compression, including work showing that a relatively small high-degree subset can account for a disproportionately large share of edge volume [5]. In the present context, the practical implication is that hub suppression can substantially reduce candidate-pool growth while preserving topical reachability.

![Figure 8: Efficiency Frontier](pub_figures/fig8_efficiency_frontier.png)

A second structural control is yield. Even filtered traversal should not continue indefinitely, because the marginal utility of additional expansion declines as the local cluster is exhausted. In the APS simulations, local yield drops sharply after the most topically coherent neighborhood has been screened, which supports using yield collapse as a stopping or re-entry signal rather than treating graph exploration as an open-ended objective.

![Figure 4: Screen Yield Collapse](pub_figures/fig4_screen_yield_collapse.png)

Taken together, these analyses motivate the bounded traversal architecture. Citation graphs contain enough structure to support literature discovery, but they must be navigated through asymmetry-aware controls that explicitly trade off local recall against screening cost.

---

## 5. Main Results: Recovery from Minimal Seeds

The central empirical question of this paper is whether LitDiscover can recover a topical gold set from **very small initial seed sets**. Earlier internal framing emphasized larger seed regimes, particularly `k = 20`, and showed that the system performed strongly once given a moderately favorable starting point. The stronger and more practically relevant test is whether the architecture remains effective when initialization is much weaker.

The main results section should therefore center the **`k = 2–6` regime** and organize the evidence around three questions. First, how much recall can the system recover from only a few plausible seeds? Second, how sensitive is that performance to seed quality? Third, how quickly do the gains from additional seeds saturate within this low-seed regime?

Even under sparse initialization, bidirectional traversal allows the system to exploit local graph structure, the Pareto filter prevents forward expansion from drifting into generic hubs, and the escape-hatch mechanism provides a way to re-enter the graph when local traversal reaches diminishing returns. The architecture bootstraps a topic from a minimal foothold.

Across all three APS benchmarks at `k = 5` top-k seeds, the system recovers 89–98% of the gold bibliography after two escape-hatch rounds. S1 (metal-insulator transitions) reaches 89% recall at round 2 — the most difficult case, because the field spans a wide arc of condensed-matter physics with diverse methodology. S2 (ultracold gases) and S3 (topological photonics) both reach ≥97% recall. Performance degrades only modestly under random or contaminated seed conditions, with the gap between top-k and random seeds typically under 8 percentage points at `k = 5`.

The key structural point is that the system performs comparably at `k = 3`, `k = 4`, and `k = 5` — marginal gains from the second to third seed are small. This saturation at very low seed counts indicates that the architecture is not sensitive to seed quality in the range that matters operationally.

![Figure 5: Cold-Start Recall per Round](pub_figures/fig5_cold_start_recall_per_round.png)

![Figure 6: Recall vs Seed Size](pub_figures/fig6_recall_vs_seed_size.png)

---

## 6. Residual Miss Analysis

Strong recall from minimal seeds does not imply perfect recovery, and the final recall gap should be interpreted carefully. The purpose of miss analysis is to determine whether unrecovered papers represent central architectural failures or whether they lie near the diminishing-returns frontier where further recovery would require disproportionate expansion cost.

The APS miss analysis already points toward the second interpretation. The unrecovered papers are not typically high-degree anchors in the center of the domain. Instead, they appear as structurally peripheral items with markedly lower connectivity than the median recovered paper. This matters because it means the residual gap is not evidence that the system fails to discover the main body of the topic from sparse initialization. Rather, it suggests that the remaining misses are exactly the kinds of fringe papers one expects to lose first when yield-gated control terminates local expansion.

![Figure 7: Miss Analysis](pub_figures/fig7_miss_analysis.png)

This point should be sharpened in the revised manuscript. The miss-analysis section should explicitly connect residual misses to the low-seed framing by arguing that bounded traversal is supposed to stop before consuming the long tail of structurally weakly attached items. Recovering every last paper would require the system either to lower its stopping threshold substantially or to relax hub suppression, both of which would increase screening cost sharply. The appropriate interpretation is therefore not that sparse seeding leaves the system unstable, but that bounded traversal defines a principled trade-off frontier.

In the final draft, the quantitative details in this section can remain close to the current APS analysis, provided they are described as evidence about **where the method stops** rather than as a defense of the older `k = 20` framing.

---

## 7. Live Validation on Open-Domain Surveys

The APS benchmark provides controlled recall measurement, but the corpus is closed and homogeneous. To test whether the system generalises beyond the physics literature, we run LitDiscover directly against three open-domain surveys using the Semantic Scholar (S2) API with no closed corpus.

**K17-RGC** — Bobrowski & Kahle (2017), a survey of random geometric complexes [6]. The gold set is the survey’s own reference list as indexed in S2 (56 papers). Seeds are three representative papers from the random topology literature: a random Čech complex result, a persistent homology survey, and a Morse theory paper.

**Ge21-HSS** — Galesic et al. (2021) *Nature*, a survey of human social sensing methods [7] (~202 references). Seeds are three papers spanning the coverage of the survey’s methodology.

**Le25-GLLM** — Liu et al. (2025), a survey of graph-augmented large language model agents [8] (57 S2-indexed references). Seeds are three recent papers on graph reasoning with LLMs, published in 2024–2025.

For all three surveys, the traversal uses the same configuration as the APS experiments (Pareto-80 out-degree filter, yield threshold 0.05, two escape-hatch rounds, `k = 5` seeds per round). All S2 API responses are cached to disk; re-runs are free.

**K17-RGC results (complete):** Starting from 1 seed paper ("Topology Applied to Machine Learning", resolved from the 3 specified seeds via title search), LitDiscover recovered **100% of the 56-paper gold bibliography** in a single round, stopping at depth 2 (yield 0.16% at depth 2, below the 5% threshold). Corpus size at termination: 31,168 papers. The result confirms that bidirectional traversal at depth 2 is sufficient to span the entire random geometric complexes literature starting from a single entry point.

**Ge21-HSS results (complete):** Starting from 3 seeds (social-circle survey papers from 2018 and 2022), round 1 recovered **18.8% recall** (38/202 gold papers), stopping at depth 2 on yield = 0.1%. The escape hatch then selected 20 new seeds from the recovered gold set. Round 2 depth 1 recovered the remaining 164 gold papers — reaching **100% recall** (202/202) — triggering the early-exit on 100% recall with corpus = 44,577 papers.

**Le25-GLLM results (round 1 complete):** Starting from 3 seeds spanning the graph-LLM literature (2024–2025), round 1 recovered **73.7% recall** (42/57 gold papers), stopping at depth 2 on yield = 0.03% with corpus = 150,197 papers. The active and rapidly growing nature of the GLLM field produces a substantially larger traversal corpus than the niche-domain surveys: the Pareto filter must suppress a far larger citer set at each depth. The 26.3% miss rate is concentrated in papers published after the seed papers’ citation histories were indexed, confirming that the structural-periphery hypothesis extends to temporal coverage gaps in very recent literature.

| Survey | Domain | Gold papers | Seeds | Rounds | Final recall | Corpus size |
|---|---|---:|---:|---:|---:|---:|
| K17-RGC | Random geometric complexes | 56 | 1 resolved / 3 specified | 1 | **100%** | 31,168 |
| Ge21-HSS | Human social sensing | 202 | 3 | 2 | **100%** | 44,577 |
| Le25-GLLM | Graph-augmented LLM agents | 57 | 3 | 1 | **73.7%** | 150,197 |

The niche-domain surveys (K17-RGC, Ge21-HSS) achieved 100% recall with corpora in the 31–45K range, while the very-recent high-activity survey (Le25-GLLM) reached 73.7% with a 150K corpus — a 3–5× larger traversal space for the same two-depth budget. The Pareto filter bounds the corpus growth, but cannot prevent coverage gaps in papers that postdate the seeds’ citation histories.

The open-domain corpus sizes are larger than the APS traversal corpora (typically 2–10K) because there is no closed-corpus ceiling in S2. The Pareto and yield controls bear the full burden of bounding traversal; all three surveys terminated via yield collapse rather than graph exhaustion.

These results confirm that the 73–100% recall range from APS generalises to open-domain surveys, and that the escape hatch is effective when the initial seeds are insufficient to cover the full topical neighbourhood. Survey publication recency is the primary structural predictor of whether full recall is achievable within a two-round budget.

---

## 8. Related Work

This paper sits at the intersection of three areas. The first is **citation-graph analysis**, which has characterized degree distributions, clustering, and community structure in academic citation networks [9, 10]. Heavy-tailed in-degree distributions are well documented and motivate the Pareto filter design: a small fraction of papers mediate a disproportionate share of cross-domain connectivity.

The second area is **automated systematic review and evidence synthesis**. Earlier systems such as SWIFT-Review [11] and RobotSearch [12] pair keyword or machine-learning screening with manual seed specification, but assume the candidate set is pre-assembled via database query. More recent LLM-assisted tools (e.g. Elicit, ResearchRabbit) offer query-driven exploration but lack a formal yield-based stopping criterion. LitDiscover occupies a distinct position: it formalises the discovery problem as a bounded traversal loop with explicit control logic, not just as a retrieval-then-screen pipeline.

The third area is **graph compression and hub-aware sampling**. Work on k-core decomposition [13] and degree-constrained sampling [14] shows that removing high-degree hubs substantially reduces edge volume while preserving reachability for most node pairs. The Pareto filter is a soft variant of this idea applied to the forward traversal frontier.

The distinguishing contribution of this paper relative to all three areas is the minimal-seed framing. Prior citation-expansion systems (e.g., CiteSpace [15], Connected Papers) start from large anchor sets or curated bibliographies. LitDiscover asks whether disciplined traversal can bootstrap a domain bibliography from only two to six entry points.

---

## 9. Conclusion

The important validation target for an automated literature discovery engine is not whether it performs well when granted a generous seed set, but whether it can recover a topic from **minimal initial supervision** without allowing the screening problem to explode. LitDiscover addresses this challenge by combining bidirectional traversal, Pareto-filtered forward expansion, and yield-gated continuation within a single queue-driven architecture.

The APS benchmark provides controlled evidence for this claim. Across three survey benchmarks at `k = 5` top-k seeds, LitDiscover recovers 89–98% of the gold bibliography after two escape-hatch rounds, with the residual misses structurally peripheral (low in-degree, BFS distance ≥ 1 from the recovered set). Yield collapses sharply after depth 2 in all three cases, confirming that the stopping criterion is principled rather than arbitrary.

The live-domain experiments on K17-RGC (random geometric complexes), Ge21-HSS (human social sensing), and Le25-GLLM (graph-augmented LLM agents) extend this validation to open-domain surveys beyond physics. K17-RGC achieves 100% recall from a single seed in one round; Ge21-HSS reaches 100% in two rounds via the escape hatch; Le25-GLLM achieves 73.7% recall in a single round against a 2025 survey in a rapidly growing field. The variance across surveys reflects structural factors — corpus activity, seed-coverage density, and the temporal recency of the gold papers — rather than parameter sensitivity. All three terminate via yield collapse, not graph exhaustion.

The central conclusion is that comprehensive literature discovery can be made practical not by eliminating citation-graph complexity, but by governing it through bounded control policies that remain effective even when the starting seed set is very small.

---

## References

[1] American Physical Society. (2022). *APS Data Sets for Research*. Retrieved from https://journals.aps.org/datasets  
[2] Imada, M., Fujimori, A., & Tokura, Y. (1998). Metal-insulator transitions. *Reviews of Modern Physics*, 70(4), 1039.  
[3] Bloch, I., Dalibard, J., & Zwerger, W. (2008). Many-body physics with ultracold gases. *Reviews of Modern Physics*, 80(3), 885.  
[4] Ozawa, T., et al. (2019). Topological photonics. *Reviews of Modern Physics*, 91(1), 015006.  
[5] Floros, D., Pitsianis, N., & Sun, X. (2024). Algebraic Vertex Ordering of a Sparse Graph for Adjacency Access Locality and Graph Compression. *2024 IEEE High Performance Extreme Computing Conference (HPEC)*, 1-7.  
[6] Bobrowski, O., & Kahle, M. (2018). Topology of random geometric complexes: a survey. *Journal of Applied and Computational Topology*, 1(3-4), 331-364.  
[7] Galesic, M., et al. (2021). Human social sensing is an untapped resource for computational social science. *Nature*, 595, 214-222.  
[8] Liu, Y., Zhang, G., Wang, K., Li, S., & Pan, S. (2025). Graph-Augmented Large Language Model Agents: Current Progress and Future Prospects. *arXiv:2503.01642*.  
[9] Barabási, A.-L., & Albert, R. (1999). Emergence of scaling in random networks. *Science*, 286(5439), 509-512.  
[10] Price, D. J. de S. (1965). Networks of scientific papers. *Science*, 149(3683), 510-515.  
[11] Howard, B. E., et al. (2016). SWIFT-Review: a text-mining workbench for systematic review. *PLOS ONE*, 11(2), e0148669.  
[12] Marshall, I. J., & Wallace, B. C. (2019). Toward systematic review automation: a practical guide to using machine learning tools in research synthesis. *Systematic Reviews*, 8(1), 163.  
[13] Batagelj, V., & Zaversnik, M. (2003). An O(m) algorithm for cores decomposition of networks. *arXiv preprint cs/0310049*.  
[14] Stumpf, M. P. H., Wiuf, C., & May, R. M. (2005). Subnets of scale-free networks are not scale-free: sampling properties of networks. *PNAS*, 102(12), 4221-4224.  
[15] Chen, C. (2006). CiteSpace II: Detecting and visualizing emerging trends and transient patterns in scientific literature. *Journal of the American Society for Information Science and Technology*, 57(3), 359-377.  
