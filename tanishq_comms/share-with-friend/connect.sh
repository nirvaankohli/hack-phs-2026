#!/usr/bin/env bash
# connect.sh - connect to the wings Pi from a Mac or Linux.
# Run:  bash connect.sh
#
# First run: makes you an SSH key and prints it. Send that line to Tanishq.
# After Tanishq adds it: run this again and you're on the Pi.

PI_IP="192.168.137.53"   # the Pi's address on Tanishq's laptop hotspot
PI_NAME="wingpi.local"
KEY="$HOME/.ssh/id_ed25519"

# 1. Make an SSH key if you don't have one
if [ ! -f "$KEY" ]; then
  mkdir -p "$HOME/.ssh"
  ssh-keygen -q -t ed25519 -N "" -C "$(whoami)-$(hostname)" -f "$KEY"
  echo "Made you an SSH key."
fi

# 2. Find the Pi
TARGET=""
if [ "$(uname)" = "Darwin" ]; then PING_WAIT="-t 2"; else PING_WAIT="-W 2"; fi  # macOS -W is in ms
for h in "$PI_IP" "$PI_NAME"; do
  if ping -c 1 $PING_WAIT "$h" >/dev/null 2>&1; then TARGET="$h"; break; fi
done
if [ -z "$TARGET" ]; then
  echo "Can't find the Pi."
  echo "  - Are you connected to Wi-Fi 'LAPTOP-LD96MHUT 6486' (Tanishq's hotspot)?"
  echo "  - Is the Pi powered on with a green light?"
  exit 1
fi

# 3. Try to log in with your key
if ! ssh -i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "pi@$TARGET" "echo OK" 2>/dev/null | grep -q OK; then
  echo
  echo "Found the Pi, but it doesn't know your key yet."
  echo "Send Tanishq this ONE line (it's safe to share, it's your public key):"
  echo
  cat "$KEY.pub"
  echo
  (command -v pbcopy >/dev/null && pbcopy < "$KEY.pub" && echo "(Already copied to your clipboard.)") || true
  echo "Once Tanishq adds it, run this script again."
  exit 0
fi

# 4. Connect
echo "Connected! You're on the Pi. Project is in ~/flappy-wings. Type 'exit' to leave."
ssh -i "$KEY" -o IdentitiesOnly=yes -t "pi@$TARGET" "cd ~/flappy-wings; exec bash -l"
