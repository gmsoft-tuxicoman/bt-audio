#!/usr/bin/bash

APP_ROOT=/usr/bin/bt-audio

echo "Installing application at '${APP_ROOT}'..."

#
# Install packages.
#

echo "Installing required packages ($PACKAGES)..."

sudo apt install -y --fix-missing \
    bluez bluez-tools \
    pulseaudio-module-bluetooth \
    gstreamer-1.0 gstreamer1.0-alsa python3-dbus dbus \
    python3 || exit 1
sudo systemctl enable bluetooth --now || exit 1

#
# Install code files
#

echo "Installing source code..."

sudo mkdir -p "${APP_ROOT}" || exit 1

sudo cp ./bt-audio.py "${APP_ROOT}/" || exit 1

sudo touch "${APP_ROOT}/run.sh" || exit 1

sudo cp run.sh "${APP_ROOT}/" || exit 1
sudo chmod +x "${APP_ROOT}/run.sh" || exit 1

#
# Install systemd service
#

echo "Installing Systemd service..."

sudo cp bt-audio.service /etc/systemd/system/ || exit 1
sudo systemctl daemon-reload || exit 1
sudo systemctl enable bt-audio --now || exit 1
sudo systemctl status bt-audio || exit 1

echo "Installation steps completed."
