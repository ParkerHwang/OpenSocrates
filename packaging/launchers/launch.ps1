param(
    [Parameter(Position = 0)]
    [string]$Mode,

    [Parameter(Position = 1)]
    [string]$HostName,

    [Parameter(Position = 2)]
    [string]$Event,

    [Parameter(Position = 3, ValueFromRemainingArguments = $true)]
    [string[]]$Extra
)

$ErrorActionPreference = "Stop"

function Pass-Through([string]$Code, [string]$LaunchMode = "", [string]$LaunchHost = "") {
    if ($LaunchMode -eq "hook" -and $LaunchHost -in @("claude", "codex")) {
        # Selector hook failures are deliberately literal empty stdout.
        exit 0
    }
    $safeCode = switch ($Code) {
        "unsupported_platform" { "unsupported_platform"; break }
        "missing_runtime" { "missing_runtime"; break }
        "invalid_arguments" { "invalid_arguments"; break }
        default { "launcher_unavailable"; break }
    }
    [Console]::Out.WriteLine('{"decision":"pass","diagnostic":{"code":"' + $safeCode + '","status":"unavailable"}}')
    exit 0
}

if ($null -ne $Extra -and $Extra.Count -gt 0) {
    Pass-Through "invalid_arguments" $Mode $HostName
}
if ([string]::IsNullOrEmpty($Mode) -or [string]::IsNullOrEmpty($HostName)) {
    Pass-Through "invalid_arguments" $Mode $HostName
}
if ($Mode -notin @("hook", "control") -or $HostName -notin @("claude", "codex")) {
    Pass-Through "invalid_arguments" $Mode $HostName
}

$validEvents = @(
    "session_started", "user_prompt_submitted", "skill_invoked", "tool_succeeded",
    "tool_failed", "tool_batch_completed", "completion_candidate", "pre_compaction",
    "post_compaction", "session_ended"
)
if ($Mode -eq "hook" -and $Event -notin $validEvents) {
    Pass-Through "invalid_arguments" $Mode $HostName
}
if ($Mode -eq "control" -and -not [string]::IsNullOrEmpty($Event)) {
    Pass-Through "invalid_arguments" $Mode $HostName
}

$isWindows = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
    [System.Runtime.InteropServices.OSPlatform]::Windows
)
if (-not $isWindows) {
    Pass-Through "unsupported_platform" $Mode $HostName
}

$architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
if ($architecture -eq "X64") {
    $relativeBinary = Join-Path (Join-Path "windows-x64" "opensocrates-runtime") "opensocrates-runtime.exe"
} else {
    Pass-Through "unsupported_platform" $Mode $HostName
}

# The generated host package places the launcher and the native runtime in
# sibling directories under the plugin root:
#
#   <plugin-root>/bin/launch.ps1
#   <plugin-root>/runtime/<target>/opensocrates-runtime/opensocrates-runtime.exe
#
# The launcher is valid only in that generated bin/ layout. Resolve exactly one
# runtime path from the plugin root, matching packaging/launchers/launch.sh; a
# moved launcher and a stray runtime tree under bin/ are unsupported.
$launcherDir = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$pluginRoot = Split-Path -Parent $launcherDir
if ([string]::IsNullOrEmpty($pluginRoot)) {
    $pluginRoot = $launcherDir
}

$runtimePath = Join-Path (Join-Path $pluginRoot "runtime") $relativeBinary
if (-not (Test-Path -LiteralPath $runtimePath -PathType Leaf)) {
    Pass-Through "missing_runtime" $Mode $HostName
}

if ($Mode -eq "hook") {
    $runtimeArgs = @("hook", $Event, "--host", $HostName)
} else {
    $runtimeArgs = @("control", "apply", "--host", $HostName)
}

if ($Mode -eq "hook") {
    & $runtimePath @runtimeArgs 2>$null
    exit 0
}

& $runtimePath @runtimeArgs
exit $LASTEXITCODE
