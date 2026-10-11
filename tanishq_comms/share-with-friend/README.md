# Connecting to the wings Pi

The Pi (`wingpi`) lives on Tanishq's laptop hotspot. You get in with your own
SSH key — no passwords.

## 1. Join the hotspot

| | |
|---|---|
| Wi-Fi name | `LAPTOP-LD96MHUT 6486` |
| Password | ask Tanishq |

Tanishq's laptop has to be on with the hotspot running, and the Pi needs a
green light.

**Without Tanishq's laptop:** a phone hotspot with the *same* name and password
works too (iPhone: rename the phone to `LAPTOP-LD96MHUT 6486` in
Settings → General → About → Name, set the same password in Personal Hotspot, and
turn on Maximize Compatibility). Join your computer to it as well. Only have one
hotspot with that name on at a time. The Pi's address will be different there;
the script finds it by name (`wingpi.local`) automatically.

## 2. Run the connect script

**Windows** — open PowerShell in this folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File connect.ps1
```

**Mac / Linux** — open Terminal in this folder and run:

```bash
bash connect.sh
```

## 3. First time only: get approved

The first run makes you an SSH key and prints one line starting with
`ssh-ed25519` (it's also copied to your clipboard). **Send that line to
Tanishq.** It's your *public* key, so it's safe to share.

Once Tanishq says you're added, run the script again. You'll land on the Pi in
`~/flappy-wings`.

## On the Pi

```bash
python3 read_test.py            # live readings from the wing sensors (Ctrl+C to stop)
python3 wings_test.py --raw     # all 4 analog ports
python3 wings_test.py --calibrate
python3 wings_test.py           # live flap detection
exit                            # leave the Pi
```

## Troubleshooting

- **"Can't find the Pi"** — check you're on the hotspot Wi-Fi above, and that
  the Pi is powered (green light). If it still fails, ask Tanishq for the Pi's
  current address and change `$PiIP` / `PI_IP` at the top of the script.
- **Still "doesn't know your key" after being added** — make sure Tanishq added
  the exact line the script printed for you.
- **Windows: "ssh is not recognized"** — Settings → System → Optional features →
  add **OpenSSH Client**.

---

### For Tanishq: approving a friend

When a friend sends you their key line, run this from this folder and paste it:

```powershell
powershell -ExecutionPolicy Bypass -File add-friend.ps1
```
