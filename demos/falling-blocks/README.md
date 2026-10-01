# Falling Blocks

A dependency-free terminal game driven by the hosted Trio-Spark API. On every
turn the environment enumerates every legal rotation and column, applies a
deterministic safety prefilter to keep at most eight candidates, and asks Spark
to choose the final move. The selected action is checked against the shortlist
before it can change the board.

## Run it

Create an API key in the [Trio-Spark console](https://platform.machinefi.com/spark#api-keys),
then run from the repository root:

```bash
export TRIO_SPARK_API_KEY=tf_...
python3 demos/falling-blocks/run.py
```

Useful options:

```bash
# Short smoke run with no terminal animation
python3 demos/falling-blocks/run.py --pieces 5 --delay 0

# Reproduce a seeded 30-piece run and choose an evidence directory
python3 demos/falling-blocks/run.py \
  --seed 61 \
  --pieces 30 \
  --output runs/falling-blocks-seed-61
```

The runner writes `decisions.jsonl` after every successful API response and a
compact `summary.json` at the end. Neither file contains the API key. The
default output is under the gitignored `runs/` directory.

## What Spark sees and controls

Spark receives:

- the current board, piece, next piece, score, and line count;
- board features such as holes, column heights, and roughness;
- 2–8 legal placements with their immediate afterstate features.

The deterministic environment owns piece generation, collision detection, line
clearing, scoring, and animation. It sorts every legal placement by immediate
line clears and basic stack safety to produce the eight-choice shortlist. That
prefilter is disclosed in the request state and does not choose the executed
move. Spark chooses within the shortlist; the environment rejects any returned
ID that was not offered.

## Recorded launch run

The repository also preserves the original measured production replay:

**30 seconds · 16 model calls · 7 lines cleared · 764 points · 0 API errors**

[Watch the run](../../assets/demos/Trio-Spark-v1.0-Falling-Blocks.mp4) ·
[Evidence](evidence.json) · [Sanitized decisions](transcript.sanitized.jsonl)

The video is a presentation replay of the recorded API responses. Running the
command above creates a fresh game against the current production model.
