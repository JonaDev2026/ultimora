# Ultimora

![Ultimora Preview](preview.png)

**Ultimora** is a modern, lightweight desktop widget written in Python using PyQt6.

## Requirements
- Python 3.8+
- Linux (GNOME/Mint/XFCE)

## Dependencies
```bash
sudo apt update
sudo apt install python3-pyqt6 python3-feedparser python3-pil
```

## Autostart (Systemd)
1. mkdir -p ~/.config/systemd/user
2. nano ~/.config/systemd/user/ultimora.service

```ini
[Unit]
Description=Ultimora Widget
After=graphical-session.target

[Service]
ExecStart=/usr/bin/python3 /home/jonathan/scripts/ultimora/ultimora.py
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

3. systemctl --user daemon-reload && systemctl --user enable --now ultimora.service
