# Paths are data in environment variables, never interpolated PowerShell code.
param([ValidateSet('entries','extract','private')][string]$Action)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$targetPath = $env:OPENSOCRATES_WINDOWS_PATH
if ($Action -eq 'private') {
    $item = Get-Item -LiteralPath $targetPath -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point refused' }
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl = $item.GetAccessControl()
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $sid.Value) { throw 'Foreign owner refused' }
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($rule in @($acl.Access)) { [void]$acl.RemoveAccessRuleSpecific($rule) }
    $inherit = if ($item.PSIsContainer) { 'ContainerInherit,ObjectInherit' } else { 'None' }
    foreach ($identity in @($sid.Value,'S-1-5-18','S-1-5-32-544')) {
        $rule = [Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($identity), 'FullControl', $inherit, 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    $item.SetAccessControl($acl)
    exit 0
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($targetPath)
try {
    $names = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $total = 0L
    foreach ($entry in $zip.Entries) {
        $name = $entry.FullName
        $parts = $name.TrimEnd('/').Split('/')
        if (!$name -or $name.Contains('\') -or $name.StartsWith('/') -or $name -match '[\x00-\x1f<>:"|?*]' -or
            ($parts | Where-Object { !$_ -or $_ -eq '.' -or $_ -eq '..' -or $_ -match '[. ]$' -or $_ -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)' }) -or !$names.Add($name.TrimEnd('/'))) { throw 'Unsafe or duplicate ZIP path' }
        if ((($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) { throw 'ZIP symlink refused' }
        $total += $entry.Length
        if ($total -gt 2147483648 -or $zip.Entries.Count -gt 20000) { throw 'ZIP limit exceeded' }
    }
    if ($Action -eq 'entries') { ConvertTo-Json -InputObject @($zip.Entries | ForEach-Object { $_.FullName }) -Compress; exit 0 }
    $destination = [IO.Path]::GetFullPath($env:OPENSOCRATES_WINDOWS_DESTINATION).TrimEnd('\') + '\'
    foreach ($entry in $zip.Entries) {
        $output = [IO.Path]::GetFullPath([IO.Path]::Combine($destination,$entry.FullName))
        if (!$output.StartsWith($destination,[StringComparison]::OrdinalIgnoreCase)) { throw 'ZIP path escape' }
        if ($entry.FullName.EndsWith('/')) { [void][IO.Directory]::CreateDirectory($output); continue }
        [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($output))
        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$output,$false)
    }
} finally { $zip.Dispose() }
