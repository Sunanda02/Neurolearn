"""
scenario_validation.py — regenerates the Scenario Validation table (§5.1
of NeuroLearn-MCL_Manuscript_Revision_Package.docx) directly from the
shipped ml/crs.py implementation. No hand-constructed numbers: every row
is the real output of compute_crs() for the listed inputs.

Run from backend/ (note: requires backend/ on PYTHONPATH):
    PYTHONPATH=. python3 scripts/scenario_validation.py
"""
from ml.crs import compute_crs

SCENARIOS = [
    ("Strong, attentive, thoughtful pace, improving", dict(
        recent_scores_pct=[60, 70, 80, 88, 92], attention_score_pct=90,
        time_spent=35, time_limit=60, was_correct=True,
        transcript_text=(
            "The recursive function calls itself with a smaller subproblem "
            "until it reaches the base case, at which point the recursion "
            "unwinds and returns the accumulated result back up the call stack."
        ),
    )),
    ("Fast + correct (the paper's own motivating case)", dict(
        recent_scores_pct=[80, 82, 85], attention_score_pct=88,
        time_spent=4, time_limit=60, was_correct=True,
        transcript_text="Short simple sentence.",
    )),
    ("Fast + wrong (legacy rule could already catch this)", dict(
        recent_scores_pct=[40, 38, 35], attention_score_pct=45,
        time_spent=4, time_limit=60, was_correct=False,
        transcript_text="Short simple sentence.",
    )),
    ("Slow / disengaged, declining trend", dict(
        recent_scores_pct=[70, 60, 50, 40], attention_score_pct=30,
        time_spent=62, time_limit=60, was_correct=False,
        transcript_text=(
            "The asynchronous middleware intercepts each request, applies "
            "dependency-injected authentication and authorization heuristics, "
            "then forwards a normalized payload downstream."
        ),
    )),
    ("No data yet (cold-start / initial difficulty)", dict()),
    ("Low behavioral_cue, high performance, thoughtful pace", dict(
        recent_scores_pct=[85, 90, 88], attention_score_pct=20,
        time_spent=40, time_limit=60, was_correct=True,
        transcript_text=(
            "Recursion, closures, and higher-order functions are core "
            "abstractions in functional programming."
        ),
    )),
]


def main():
    header = f'{"Scenario":48s} {"P":>5} {"A":>5} {"I":>5} {"T":>5} {"C":>5} {"CRS":>6} {"Tier":>7}'
    print(header)
    print("-" * len(header))
    for name, kwargs in SCENARIOS:
        r = compute_crs(**kwargs)
        c = r.components
        print(
            f"{name:48s} {c.performance:5.2f} {c.behavioral_cue:5.2f} "
            f"{c.integrity:5.2f} {c.trend:5.2f} {c.complexity:5.2f} "
            f"{r.crs:6.3f} {r.difficulty:>7s}"
        )


if __name__ == "__main__":
    main()
