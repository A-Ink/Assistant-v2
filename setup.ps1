Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  N7 TERMINAL : AUTOMATED DEPLOYMENT SCRIPT" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1. Check Python
Write-Host "`n[*] Verifying Python 3.11 Environment..."
if (!(Get-Command "py" -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Python Launcher 'py' not found. Please install Python 3.11 from python.org." -ForegroundColor Red
    Pause
    exit
}

# 2. Virtual Environment
Write-Host "[*] Initializing Virtual Environment..."
if (!(Test-Path ".venv")) {
    py -3.11 -m venv .venv
    Write-Host "[OK] Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "[*] Virtual environment already exists." -ForegroundColor Yellow
}

Write-Host "[*] Upgrading pip..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "[*] Installing core dependencies (OpenVINO, UI, etc.)..."
.\.venv\Scripts\pip install -r requirements.txt

# 3. Llama.cpp Interactive Prompt
Write-Host "`n==============================================" -ForegroundColor Yellow
Write-Host "  LLAMA.CPP VULKAN ENGINE OPTION" -ForegroundColor Yellow
Write-Host "==============================================" -ForegroundColor Yellow
Write-Host "To run GGUF models on your Intel Arc or iGPU, the Vulkan Engine is required."
Write-Host "This requires the Vulkan SDK and a C++ Compiler (Visual Studio Build Tools)."
$response = Read-Host "Would you like to compile and install the Llama.cpp Vulkan Engine? (Y/N)"

if ($response -match "^[yY]") {
    Write-Host "`n[*] Starting Native Vulkan Compilation..." -ForegroundColor Cyan
    
    # VS Build Tools setup for Vulkan
    $vsPath = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vs_installer.exe"
    if (!(Test-Path $vsPath)) {
        Write-Host "[!] VS Build Tools not found. Attempting to install via winget..."
        winget install Microsoft.VisualStudio.2022.BuildTools --force --override "--passive --wait --add Microsoft.VisualStudio.Workload.VCTools" --accept-package-agreements --accept-source-agreements
    }

    Write-Host "`n[*] Compiling llama-cpp-python with Vulkan support..." -ForegroundColor Cyan
    $env:CMAKE_ARGS = "-DGGML_VULKAN=on"
    .\.venv\Scripts\python.exe -m pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir
    
    Write-Host "`n[SUCCESS] Vulkan Llama.cpp Engine established!" -ForegroundColor Green
} else {
    Write-Host "`n[*] Skipping Vulkan Engine. OpenVINO (NPU) models will function as the primary backend." -ForegroundColor Cyan
}

Write-Host "`n==============================================" -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "1. Activate venv: .\.venv\Scripts\Activate.ps1"
Write-Host "2. Download models: python download_model.py"
Write-Host "3. Launch Terminal: python main.py"
Write-Host "==============================================" -ForegroundColor Green
Pause
