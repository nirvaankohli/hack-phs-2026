# add-friend.ps1 - FOR TANISHQ: let a friend's SSH key into the Pi.
# Run:  powershell -ExecutionPolicy Bypass -File add-friend.ps1
# Then paste the line your friend sent you (starts with "ssh-ed25519" or "ssh-rsa").

param([string]$Key)

$PiIP = "192.168.137.53"
$ssh  = "$env:WINDIR\System32\OpenSSH\ssh.exe"

if (-not $Key) { $Key = Read-Host "Paste your friend's key line" }
$Key = $Key.Trim()
if ($Key -notmatch '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-\S+) [A-Za-z0-9+/=]+( .*)?$') {
    Write-Host "That doesn't look like an SSH public key. It should start with ssh-ed25519 or ssh-rsa." -ForegroundColor Red
    exit 1
}

# Append to the Pi's authorized_keys, skipping it if it's already there
# (no double quotes in $remote: Windows PowerShell strips them when calling ssh.exe)
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Key + "`n"))
$remote = "mkdir -p ~/.ssh; chmod 700 ~/.ssh; touch ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys; " +
          "echo $b64 | base64 -d > /tmp/newkey; sed -i -e '`$a\' ~/.ssh/authorized_keys; " +
          "if grep -qxFf /tmp/newkey ~/.ssh/authorized_keys; then echo ALREADY; else cat /tmp/newkey >> ~/.ssh/authorized_keys; echo ADDED; fi"
$out = & $ssh -o BatchMode=yes -o ConnectTimeout=8 "pi@$PiIP" $remote 2>&1
switch -Regex ("$out") {
    "ADDED"   { Write-Host "Added. Tell your friend to run connect again." -ForegroundColor Green }
    "ALREADY" { Write-Host "That key was already on the Pi." -ForegroundColor Green }
    default   { Write-Host "Couldn't reach the Pi: $out" -ForegroundColor Red }
}
