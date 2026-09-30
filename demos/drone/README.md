# Autonomous drone

Trio-Spark receives structured flight state and chooses one of six tactical maneuvers. A separate high-frequency reflex layer retains collision avoidance.

## Reproduce

```bash
git clone https://github.com/RomanSlack/jev-drone.git
cd jev-drone
git checkout 974b47378c14c6dcf7d11f7c813fba0f5f4d8b6a
git apply ../trio-spark.patch
python -m venv .venv && .venv/bin/pip install -r requirements.txt
export TRIO_SPARK_API_KEY=tf_...
MUJOCO_GL=egl .venv/bin/python run.py --seconds 65 --seeds 1 --video drone.mp4 --hz 0.65 --budget 44
```

The published run crossed the full obstacle course with 0 collisions. The production API made 25 successful decisions with 0 errors; median wall latency was 0.933 s and p90 was 1.049 s.
