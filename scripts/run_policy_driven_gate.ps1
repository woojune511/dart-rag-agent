[CmdletBinding()]
param(
    [string]$Config = "benchmarks/profiles/curated_policy_driven_runtime_gate.json",
    [string]$OutputDir = ("benchmarks/results/policy_gate_release_" + (Get-Date -Format "yyyy-MM-dd_HHmmss")),
    [string[]]$CompanyRunId = @(
        "naver_2023_policy_driven_runtime_gate",
        "hyundai_2023_policy_driven_runtime_gate",
        "lge_2023_policy_driven_runtime_gate",
        "samsung_2023_policy_driven_runtime_gate"
    ),
    [string]$Python = ".\.venv\Scripts\python.exe",
    [switch]$SingleProcess,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$ResolvedPython = $Python
if (-not (Test-Path $ResolvedPython) -and -not (Get-Command $ResolvedPython -ErrorAction SilentlyContinue)) {
    if ($Python -eq ".\.venv\Scripts\python.exe") {
        $ResolvedPython = "python"
    } else {
        throw "Python executable not found: $Python"
    }
}

function Format-CommandLine {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    $DisplayArgs = $Arguments | ForEach-Object {
        if ($_ -match "\s") {
            '"' + ($_ -replace '"', '\"') + '"'
        } else {
            $_
        }
    }
    return "$Executable $($DisplayArgs -join ' ')"
}

function Invoke-PolicyGateRunner {
    param(
        [string[]]$RunIds
    )

    $RunnerArgs = @(
        "-m",
        "src.ops.benchmark_runner",
        "--config",
        $Config,
        "--output-dir",
        $OutputDir
    )

    foreach ($RunId in $RunIds) {
        $RunnerArgs += @("--company-run-id", $RunId)
    }

    $CommandLine = Format-CommandLine -Executable $ResolvedPython -Arguments $RunnerArgs
    if ($DryRun) {
        Write-Host "[dry-run] $CommandLine"
        return
    }

    Write-Host "[policy-gate] $CommandLine"
    & $ResolvedPython @RunnerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Policy gate runner failed with exit code $LASTEXITCODE"
    }
}

if ($SingleProcess) {
    Invoke-PolicyGateRunner -RunIds $CompanyRunId
} else {
    foreach ($RunId in $CompanyRunId) {
        Invoke-PolicyGateRunner -RunIds @($RunId)
    }
}

if (-not $DryRun) {
    Write-Host "[policy-gate] completed: $OutputDir"
}
