# connect.ps1 - connect to the wings Pi from Windows.
# Run:  powershell -ExecutionPolicy Bypass -File connect.ps1
#
# First run: makes you an SSH key and prints it. Send that line to Tanishq.
# After Tanishq adds it: run this again and you're on the Pi.

$PiIP   = "192.168.137.53"   # the Pi's address on Tanishq's laptop hotspot
$PiName = "wingpi.local"
$Key    = "$env:USERPROFILE\.ssh\id_ed25519"
$ssh    = "$env:WINDIR\System32\OpenSSH\ssh.exe"
$keygen = "$env:WINDIR\System32\OpenSSH\ssh-keygen.exe"

if (-not (Test-Path $ssh)) {
    Write-Host "OpenSSH isn't installed. Settings > System > Optional features > Add 'OpenSSH Client', then run this again." -ForegroundColor Red
    exit 1
}

# 1. Make an SSH key if you don't have one
if (-not (Test-Path $Key)) {
    New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
    Start-Process $keygen -ArgumentList "-q -t ed25519 -N `"`" -C `"$env:USERNAME-$env:COMPUTERNAME`" -f `"$Key`"" -Wait -NoNewWindow
    Write-Host "Made you an SSH key." -ForegroundColor Green
}

# 2. Find the Pi
$target = $null
foreach ($h in @($PiIP, $PiName)) {
    if (Test-Connection -ComputerName $h -Count 1 -Quiet -ErrorAction SilentlyContinue) { $target = $h; break }
}
if (-not $target) {
    Write-Host "Can't find the Pi." -ForegroundColor Red
    Write-Host "  - Are you connected to Wi-Fi 'LAPTOP-LD96MHUT 6486' (Tanishq's hotspot)?"
    Write-Host "  - Is the Pi powered on with a green light?"
    exit 1
}

# 3. Try to log in with your key
$check = & $ssh -i $Key -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "pi@$target" "echo OK" 2>&1
if ("$check" -notmatch "OK") {
    Write-Host ""
    Write-Host "Found the Pi, but it doesn't know your key yet." -ForegroundColor Yellow
    Write-Host "Send Tanishq this ONE line (it's safe to share, it's your public key):" -ForegroundColor Yellow
    Write-Host ""
    Get-Content "$Key.pub"
    Write-Host ""
    Get-Content "$Key.pub" | Set-Clipboard
    Write-Host "(Already copied to your clipboard.) Once Tanishq adds it, run this script again." -ForegroundColor Yellow
    exit 0
}

# 4. Connect
Write-Host "Connected! You're on the Pi. Project is in ~/flappy-wings. Type 'exit' to leave." -ForegroundColor Green
& $ssh -i $Key -o IdentitiesOnly=yes -t "pi@$target" "cd ~/flappy-wings; exec bash -l"
