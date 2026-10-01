# Public evaluation harness

This harness sends pinned public benchmark splits through the same hosted
Trio-Spark API available to every developer. It records enough provenance to
reproduce a run without exposing the API key.

## What it measures

Every completed run writes:

- `manifest.json` — dataset revision, fingerprint, model ID, code commit, and environment;
- `raw.jsonl` — one append-only record per decision, safe to resume after interruption;
- `summary.json` — accuracy, ECE, Brier score, NLL, p50/p95 service and wall latency,
  valid-output rate, billed input tokens, cost, model version, and repeat stability.

The supported frozen tasks are:

| CLI name | Dataset | Split | Choices |
|---|---|---|---:|
| `sst2` | `nyu-mll/glue` | validation | 2 |
| `sst5` | `SetFit/sst5` | test | 5 |
| `ag-news` | `fancyzhx/ag_news` | test | 4 |
| `tweet-offensive` | `cardiffnlp/tweet_eval` | test | 2 |
| `pubmedqa` | `qiaojin/PubMedQA` PQA-L | train | 3 |
| `jevals` | Jevals 0.1.0 PubMedQA | frozen 300 × 5 | 2 |

All Hugging Face revisions are immutable commit hashes in `run.py`. The vendored
Jevals manifest is from `Jevals/jevals-data` commit
`21bb47b72814cf661539b313844d2d2e26166e54` and remains CC-BY-4.0.

## Run a smoke

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r evals/requirements.txt
export TRIO_SPARK_API_KEY=tf_...

python3 evals/run.py \
  --benchmark sst2 \
  --limit 10 \
  --output runs/sst2-smoke
```

Inspect `summary.json` before starting a paid full split. The default 1.1-second
pace keeps requests serial and below 60 starts per minute. Production may return
a stricter account rate limit; the runner honors retryable errors and
`Retry-After`, persists each completed response immediately, and safely resumes
when the same command is run again.

## Full runs

Remove `--limit` to score the complete pinned split:

```bash
python3 evals/run.py --benchmark sst2 --output runs/sst2-full
python3 evals/run.py --benchmark sst5 --output runs/sst5-full
python3 evals/run.py --benchmark ag-news --output runs/ag-news-full
python3 evals/run.py --benchmark tweet-offensive --output runs/tweet-offensive-full
python3 evals/run.py --benchmark pubmedqa --output runs/pubmedqa-full
python3 evals/run.py --benchmark jevals --output runs/jevals-pubmedqa
```

Jevals runs default to five epochs, matching suite 0.1.0. A `--limit` applies to
the number of unique items before repeats.

## Comparability rules

- A full score is comparable only at 100% planned coverage. Partial runs still
  report diagnostics but set `comparable_overall=false`.
- The runner stops on the first terminal error. It never silently drops a hard
  request and reports a higher valid-only score.
- Banking77 and CLINC150 are intentionally absent. They have 77 and 150 labels,
  while the production contract accepts 2–8 choices. Oracle shortlists or
  tournaments would measure a different task.
- PubMedQA and Jevals PubMedQA use different protocols. The three-choice full
  split score must not be presented as the two-choice Jevals score.
- Network wall time and service-reported model latency are separate fields.
- `TRIO_SPARK_API_KEY` is read only from the environment and is never written.

If scoring logic changes after collection, recompute a complete run without
another inference pass:

```bash
python3 evals/rescore.py runs/sst2-full
```
