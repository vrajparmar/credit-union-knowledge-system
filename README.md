# Snapshot knowledge-system submission

This project answers credit-union questions using the supplied website snapshots.
It selects the requested date, matches product terms and tiers, cites supporting
pages, and reports disagreements between comparable rate observations.

The canonical submission is **`submission/`**. Point the evaluator at this folder.
`hackathon-knowledge-kit-participant/submission/` is a compatibility copy for the
original kit layout; the regression suite verifies that both copies match.

## Requirements

- Python 3.11 (the assignment's grading version).
- No third-party packages, API keys, or network calls are needed for the solution.
- The authorized website dataset is needed only for the full public evaluation.

## Run from a clean checkout

Run these commands from the repository root. The synthetic regression fixtures
and official synthetic self-test are included, so these checks need no website
dataset:

```sh
python3.11 -B -m unittest discover -s tests -v
python3.11 -B hackathon-knowledge-kit-participant/harness/run_eval.py \
  --submission submission \
  --snapshots hackathon-knowledge-kit-participant/harness/selftest/snapshots \
  --eval hackathon-knowledge-kit-participant/harness/selftest/eval.jsonl \
  --conflicts-gold hackathon-knowledge-kit-participant/harness/selftest/conflicts_gold.json \
  --out results/selftest
```

Obtain the website snapshots from the authorized participant kit. Keep the
expanded dataset outside this repository, or restore it locally to the kit's
ignored `snapshots/` directory. The directory passed to `--snapshots` must contain
the dated snapshot folders, each with a `manifest.json` and `pages/` directory.
Do not publish the real website snapshots or their ZIP archives.

```sh
python3.11 -B hackathon-knowledge-kit-participant/harness/run_eval.py \
  --submission submission \
  --snapshots /path/to/authorized/snapshots \
  --eval hackathon-knowledge-kit-participant/eval/public_eval.jsonl \
  --out results/public
```

The unchanged public scorer cannot grade `dup-005` offline because that item's
`must_include` list is empty. Its optional semantic judge needs separate setup;
the solution itself does not. A 0.9690 public score with only this item ungraded
must not be interpreted as a hidden-test score or complete conflict coverage.
Use the self-test conflict gold only with the self-test dataset.

## Development

Edit `submission/`, then synchronize the compatibility copy before testing:

```sh
cp submission/solution.py submission/NOTES.md submission/requirements.txt \
  hackathon-knowledge-kit-participant/submission/
python3.11 -B -m unittest discover -s tests -v
```

The regression tests cover term paraphrases, calendar boundaries, historical
answers, source precedence, changed rates, conflict provenance, branch identity,
mortgage programs and amount tiers, personal/auto loan separation, checking
balance bands, card identities, jumbo negation, and packaging consistency.
They also check savings balance boundaries, dividend/APY separation, unknown
account names, flex/fixed certificates, abbreviated and year-only dates, short
branch requests, and card fees/introductory offers using changed source data.
Additional regressions cover decimal terms, signed balances, unsupported card
and mortgage identities, branch-and-city matching, future vehicle years,
multi-part card questions, and unresolved loan conflicts under reversed page
order. Supported products and changed/historical source values are tested too.
The official harness and public evaluation files are unchanged.
See `submission/NOTES.md` for design choices and coverage limits.
