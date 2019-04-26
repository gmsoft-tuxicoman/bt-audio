# bt-audio

This python script will turn your linux PC into a bluetooth speaker.
It allows your devices (phone, tablet, etc) to connect without authentication to the PC and play the sound to your alsa card.

## Requirements
* Bluez 5.x
* Gstreamer
  * bluez plugin (avdtpsrc)
  * SBC codec (rtpsbcdepay, sbcparse, sbcdec)


## Bluez configuration

### /etc/bluetooth/main.conf

```
# This will show a nice 'speaker icon' on your phone/tablet
# Sometimes bluez override this, you can disable it by starting bluetoothd with `-P hostname`
Class = 0x000414

# Make your PC always discoverable
DiscoverableTimeout = 0

# Make your pC always pairable
PairableTimeout = 0
```

This script has not been tested along with other bluetooth software. It might not work if you have another bluetooth manager running on your pc. This is intended for headless server.
