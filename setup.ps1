$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.10–3.13 from python.org, then retry.' }
}
& '.\.venv\Scripts\python.exe' -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw 'CUDA runtime installation failed.' }
& '.\.venv\Scripts\python.exe' -m pip install --no-cache-dir -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Application dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -c "import torch; print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA unavailable')"
Write-Host 'Ready. Double-click Launch HMR Upscale.vbs.'
