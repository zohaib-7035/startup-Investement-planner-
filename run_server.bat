@echo off
set USE_TF=0
set USE_TORCH=1
set TOKENIZERS_PARALLELISM=false
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
cd /d Z:\claude\stock_analyzer
Z:\python39\python.exe app.py
