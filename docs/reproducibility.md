# Reproducibility

Experiment B runs one model per process. To evaluate several configured models in PowerShell,
run the following loop; each invocation writes its own run directory:

```powershell
$models = @("bge-small-en-v1.5", "Qwen3-Embedding-0.6B", "bge-m3", "nomic-embed-text-v1.5")
foreach ($model in $models) {
    python scripts/05_run_exp_b.py --model $model --chunking section_aware --split dev
}
```
