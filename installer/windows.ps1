# Paths are data in environment variables, never interpolated PowerShell code.
param([ValidateSet('entries','extract','private','check','check-tree','mkdir-private','seal-new','lease')][string]$Action)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
function Native-Path([string]$path) {
    $absolute = [IO.Path]::GetFullPath($path)
    # PowerShell 5.1's FileSystemInfo ACL methods otherwise fail beyond MAX_PATH,
    # including an owned tree temporarily moved below a transaction backup.
    # Convert an already absolute local drive path; caller path/alias policy and
    # every ownership, DACL and reparse check remain in force.
    if ($absolute -match '^[a-zA-Z]:\\') { return '\\?\' + $absolute }
    return $absolute
}
$targetPath = Native-Path $env:OPENSOCRATES_WINDOWS_PATH
$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentSid = $currentIdentity.User
$trustedSids = @($currentSid.Value,'S-1-5-18','S-1-5-32-544')
function Assert-Parents([string]$path) {
    $cursor = [IO.Path]::GetFullPath($path)
    while ($cursor) {
        $item = Get-Item -LiteralPath $cursor -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse ancestor refused' }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
}
function Private-Acl([bool]$directory) {
    $acl = if ($directory) { [Security.AccessControl.DirectorySecurity]::new() } else { [Security.AccessControl.FileSecurity]::new() }
    $acl.SetOwner($currentSid)
    $acl.SetAccessRuleProtection($true,$false)
    $inherit = if ($directory) { 'ContainerInherit,ObjectInherit' } else { 'None' }
    foreach ($identity in $trustedSids) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($identity),'FullControl',$inherit,'None','Allow'))
    }
    return $acl
}
function Assert-Owned($item) {
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point refused' }
    $acl = $item.GetAccessControl()
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $currentSid.Value) { throw 'Foreign owner refused' }
    $writes = [Security.AccessControl.FileSystemRights]::Write -bor [Security.AccessControl.FileSystemRights]::Delete -bor [Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor [Security.AccessControl.FileSystemRights]::ChangePermissions -bor [Security.AccessControl.FileSystemRights]::TakeOwnership
    foreach ($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
        if ($rule.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly) { continue }
        if ($rule.AccessControlType -eq 'Allow' -and ($rule.FileSystemRights -band $writes) -and $rule.IdentityReference.Value -notin $trustedSids) { throw 'Untrusted writable DACL refused' }
    }
}
function Tree-Items($rootItem) {
    $pending = [Collections.Generic.Queue[IO.FileSystemInfo]]::new()
    $pending.Enqueue($rootItem)
    $count = 0
    while ($pending.Count) {
        $item = $pending.Dequeue()
        if (++$count -gt 20000) { throw 'Filesystem limit exceeded' }
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point refused' }
        $item
        if ($item -is [IO.DirectoryInfo]) {
            foreach ($child in $item.EnumerateFileSystemInfos()) { $pending.Enqueue($child) }
        }
    }
}
if ($Action -eq 'mkdir-private') {
    if (Test-Path -LiteralPath $targetPath) { throw 'New private directory collision' }
    Assert-Parents ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($targetPath)))
    ([IO.DirectoryInfo]::new($targetPath)).Create((Private-Acl $true))
    Assert-Owned (Get-Item -LiteralPath $targetPath -Force)
    exit 0
}
if ($Action -in @('check','check-tree','seal-new','lease')) {
    Assert-Parents $targetPath
    $rootItem = Get-Item -LiteralPath $targetPath -Force
    if ($Action -eq 'seal-new') {
        # Caller uses this only for an exclusively created staging tree/file.
        $items = @(Tree-Items $rootItem)
        foreach ($item in $items) {
            $owner = $item.GetAccessControl().GetOwner([Security.Principal.SecurityIdentifier]).Value
            if ($owner -notin @($currentSid.Value,$currentIdentity.Owner.Value)) { throw 'Foreign staging owner refused' }
        }
        foreach ($item in $items) { $item.SetAccessControl((Private-Acl ($item -is [IO.DirectoryInfo]))) }
    } elseif ($Action -eq 'check-tree') {
        foreach ($item in (Tree-Items $rootItem)) { Assert-Owned $item }
    } else { Assert-Owned $rootItem }
    if ($Action -ne 'lease') { exit 0 }
    # Pin ancestors without FILE_SHARE_DELETE while Node holds its operation lock.
    Add-Type @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class OpenSocratesDirectoryLease {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  public static extern SafeFileHandle CreateFile(string name, uint access, uint share, IntPtr security, uint mode, uint flags, IntPtr template);
}
'@
    $handles = [Collections.Generic.List[Microsoft.Win32.SafeHandles.SafeFileHandle]]::new()
    try {
        $cursor = [IO.Path]::GetFullPath($targetPath)
        while ($cursor) {
            # FILE_LIST_DIRECTORY establishes read sharing; access=0 does not
            # participate in deletion sharing and cannot protect against rename.
            $handle = [OpenSocratesDirectoryLease]::CreateFile($cursor,1,3,[IntPtr]::Zero,3,0x02200000,[IntPtr]::Zero)
            if ($handle.IsInvalid) { throw 'Cannot pin managed ancestor' }
            $handles.Add($handle)
            $cursor = [IO.Path]::GetDirectoryName($cursor)
        }
        Assert-Parents $targetPath
        Assert-Owned (Get-Item -LiteralPath $targetPath -Force)
        [Console]::WriteLine('ready')
        [Console]::Out.Flush()
        [void][Console]::In.ReadLine()
    } finally { foreach ($handle in $handles) { $handle.Dispose() } }
    exit 0
}
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
Assert-Parents $targetPath
$zip = [IO.Compression.ZipFile]::OpenRead($targetPath)
try {
    $names = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $directories = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $total = 0L
    foreach ($entry in $zip.Entries) {
        $name = $entry.FullName
        if ($name.EndsWith('/')) { [void]$directories.Add($name.TrimEnd('/')) }
        $parts = $name.TrimEnd('/').Split('/')
        if (!$name -or $name.Contains('\') -or $name.StartsWith('/') -or $name -match '[\x00-\x1f<>:"|?*]' -or
            ($parts | Where-Object { !$_ -or $_ -eq '.' -or $_ -eq '..' -or $_ -match '[. ]$' -or $_ -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)' }) -or !$names.Add($name.TrimEnd('/'))) { throw 'Unsafe or duplicate ZIP path' }
        $kind = ($entry.ExternalAttributes -shr 16) -band 0xF000
        if ($kind -notin @(0,0x4000,0x8000) -or ($entry.ExternalAttributes -band 0x400)) { throw 'ZIP non-regular entry refused' }
        if ($kind -eq 0x4000 -and !$name.EndsWith('/')) { throw 'ZIP directory type mismatch' }
        $total += $entry.Length
        if ($total -gt 2147483648 -or $zip.Entries.Count -gt 20000) { throw 'ZIP limit exceeded' }
    }
    foreach ($entry in $zip.Entries) {
        $parentName = $entry.FullName.TrimEnd('/')
        while ($parentName.Contains('/')) {
            $parentName = $parentName.Substring(0,$parentName.LastIndexOf('/'))
            if ($names.Contains($parentName) -and !$directories.Contains($parentName)) { throw 'ZIP file-directory collision' }
        }
    }
    if ($Action -eq 'entries') { ConvertTo-Json -InputObject @($zip.Entries | ForEach-Object { $_.FullName }) -Compress; exit 0 }
    $destination = (Native-Path $env:OPENSOCRATES_WINDOWS_DESTINATION).TrimEnd('\') + '\'
    Assert-Parents $destination
    foreach ($entry in $zip.Entries) {
        # Extended Win32 paths do not translate the ZIP's portable slash syntax.
        $output = [IO.Path]::GetFullPath([IO.Path]::Combine($destination,$entry.FullName.Replace('/','\')))
        if (!$output.StartsWith($destination,[StringComparison]::OrdinalIgnoreCase)) { throw 'ZIP path escape' }
        if ($entry.FullName.EndsWith('/')) { [void][IO.Directory]::CreateDirectory($output); continue }
        [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($output))
        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$output,$false)
    }
} finally { $zip.Dispose() }
