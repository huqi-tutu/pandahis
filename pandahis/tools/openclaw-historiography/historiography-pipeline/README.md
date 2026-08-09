# historiography-pipeline（单卷流水线脚本）

本目录存放**可执行流水线**（`run_volume_pipeline.py`、`hist_gates.py` 等），支持 v2 轨道：

```bash
export HIST_ANNOTATE_TRACK=v2
python3 run_volume_pipeline.py --track v2 next --work 01史记
python3 run_volume_pipeline.py --track v2 verify --work 01史记 --vol 001 --step 1
```

**Agent 调度说明（唯一）** → [`../historiography-pipeline-v2/SKILL.md`](../historiography-pipeline-v2/SKILL.md)

老版 v1 调度 Skill（`SKILL.md`）已移除。
