"""
Phase 9: Elbow Detection / Early Stopping Analysis

This script analyzes the per-round results from the cold-start simulation
to determine if an "elbow" stopping criterion can effectively halt the
Escape Hatch loop early, saving screening costs without significantly
sacrificing recall.

It evaluates criteria such as:
- Marginal recall gain < threshold
- Absolute new gold papers < threshold
- Round-level screen yield (new_gold / new_nodes) < threshold

Because the cold-start simulation already saves per-round statistics,
this extension is entirely self-contained and requires no re-computation
of the graph traversals.
"""

import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

_REPO = Path(__file__).parent.parent.parent
OUT = _REPO / "data" / "outputs"
FIGS = OUT / "pub_figures"
FIGS.mkdir(parents=True, exist_ok=True)

def evaluate_stopping_rule(cold_data, rule_func, rule_name):
    """
    Evaluates a stopping rule across all surveys and seed conditions.
    rule_func takes a list of round dicts and returns the index (0-based) of the round to stop at.
    """
    results = []
    for survey, conditions in cold_data.items():
        for seed_type, sizes in conditions.items():
            for k_str, rounds in sizes.items():
                if not rounds:
                    continue
                
                stop_idx = rule_func(rounds)
                
                final_round_actual = rounds[-1]
                final_round_stopped = rounds[stop_idx]
                
                results.append({
                    "survey": survey,
                    "seed_type": seed_type,
                    "k": int(k_str),
                    "rule": rule_name,
                    "actual_rounds": len(rounds),
                    "stopped_round": stop_idx + 1,
                    "actual_recall": final_round_actual["recall"],
                    "stopped_recall": final_round_stopped["recall"],
                    "actual_corpus": final_round_actual["corpus_size"],
                    "stopped_corpus": final_round_stopped["corpus_size"],
                    "recall_loss": final_round_actual["recall"] - final_round_stopped["recall"],
                    "corpus_saved": final_round_actual["corpus_size"] - final_round_stopped["corpus_size"]
                })
    return pd.DataFrame(results)

def main():
    try:
        with open(OUT / "cold_start_results.json") as f:
            cold = json.load(f)
    except FileNotFoundError:
        print("cold_start_results.json not found. Please run 04_cold_start_simulation.py first.")
        return

    # Define stopping rules
    # Rule 1: Stop if marginal recall gain in the round is < 1%
    def rule_marginal_recall_1pct(rounds):
        for i, r in enumerate(rounds):
            if i == 0: continue
            prev_recall = rounds[i-1]["recall"]
            if r["recall"] - prev_recall < 0.01:
                return i - 1 # Stop at previous round
        return len(rounds) - 1

    # Rule 2: Stop if new gold papers found in the round < 5
    def rule_new_gold_lt_5(rounds):
        for i, r in enumerate(rounds):
            if i == 0: continue # Always complete at least round 1
            if r["new_gold"] < 5:
                return i - 1
        return len(rounds) - 1

    # Rule 3: Stop if round-level screen yield < 0.01
    def rule_round_yield_lt_1pct(rounds):
        for i, r in enumerate(rounds):
            if i == 0: continue
            yield_val = r["new_gold"] / r["new_nodes"] if r["new_nodes"] > 0 else 0
            if yield_val < 0.01:
                return i - 1
        return len(rounds) - 1

    rules = {
        "Marginal Recall < 1%": rule_marginal_recall_1pct,
        "New Gold < 5": rule_new_gold_lt_5,
        "Round Yield < 1%": rule_round_yield_lt_1pct
    }

    all_results = []
    for name, func in rules.items():
        df = evaluate_stopping_rule(cold, func, name)
        all_results.append(df)
    
    df_all = pd.concat(all_results, ignore_index=True)
    
    # Summarize results
    summary = df_all.groupby("rule").agg({
        "stopped_round": "mean",
        "recall_loss": "mean",
        "corpus_saved": "mean"
    }).reset_index()
    
    print("=== Early Stopping Rule Summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    
    # Save detailed results
    df_all.to_csv(OUT / "elbow_stopping_results.csv", index=False)
    print(f"\nDetailed results saved to {OUT / 'elbow_stopping_results.csv'}")

    # Generate a plot comparing the rules
    fig, ax = plt.subplots(figsize=(8, 5))
    
    # Plot average recall loss vs corpus saved for each rule
    for _, row in summary.iterrows():
        ax.scatter(row["corpus_saved"], row["recall_loss"], s=100, label=row["rule"])
        ax.annotate(row["rule"], (row["corpus_saved"], row["recall_loss"]), 
                    xytext=(5, 5), textcoords='offset points')
        
    ax.set_xlabel("Average Corpus Saved (nodes)")
    ax.set_ylabel("Average Recall Loss")
    ax.set_title("Efficiency of Early Stopping Rules")
    ax.grid(True, linestyle="--", alpha=0.6)
    
    fig.tight_layout()
    fig.savefig(FIGS / "fig9_elbow_stopping_efficiency.png", dpi=150)
    plt.close(fig)
    print(f"Saved figure to {FIGS / 'fig9_elbow_stopping_efficiency.png'}")

if __name__ == "__main__":
    main()
