# GGWave audio plugin

This is an OVOS audio transformer plugin for [ggwave](https://github.com/ggerganov/ggwave). It decodes audio QR codes (sound-based data messages) heard by the microphone and acts on them.

You can test the plugin from your [browser](https://openvoiceos.github.io/ovos-audio-transformer-plugin-ggwave/), including WiFi setup.

The companion skill [OpenVoiceOS/ovos-skill-ggwave](https://github.com/OpenVoiceOS/ovos-skill-ggwave) lets you enable or disable this plugin by voice.

These skill stores support installing skills through GGWave:
- [OVOS-skills-store](https://openvoiceos.github.io/OVOS-skills-store)
- [OVOS-Hatchery-skills](https://ovoshatchery.github.io/OVOS-Hatchery-skills)

To install skills this way, allow ovos-core to install Python packages:

```javascript
"skills": {
    "installer": {
      "allow_pip": true,
      "allow_alphas": true,
      "break_system_packages": false
    }
}
```

> **TIP** Allow ovos-core to install Python packages. Otherwise the install commands from this plugin fail.

## Install

```bash
pip install ovos-audio-transformer-plugin-ggwave
```

> ggwave [fails to install on Python 3.11](https://github.com/ggerganov/ggwave/issues/89). Use the wheel from [whl.smartgic.io](https://whl.smartgic.io/) instead, then the plugin install works.

## Listener plugin

To load this plugin from dinkum-listener, enable it in `mycroft.conf`.

> **WARNING** This is currently not recommended. See the [bug report in dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener/issues/98).

```javascript
"listener": {
    "audio_transformers": {
        "ovos-audio-transformer-plugin-ggwave": {
            "start_enabled": true,
            "listen_timeout": 300
        }
    }
}
```

`listen_timeout` (seconds, default `300`) auto-disables the listener after it
has been enabled over the bus with `ovos.ggwave.enable`, so a stray or
forgotten enable does not leave data-over-sound listening on forever. This is
a security default: an enabled listener can trigger opcodes such as `BUS:`,
`PIP:`, and `GHS:` (install a skill from a GitHub URL) for anyone in earshot.
Set it to `0` (or a negative number) to disable this behavior and listen
indefinitely once enabled. It has no effect on `start_enabled`: enabling the
listener via config is an explicit operator decision to run always-on, and
does not arm the timer.

## Valid audio data

This repo provides a test interface on [GitHub Pages](https://openvoiceos.github.io/ovos-audio-transformer-plugin-ggwave/). You can also test your own payloads at [ggwave-js.ggerganov.com](https://ggwave-js.ggerganov.com/).

### WiFi setup

Emit a message that sets the WiFi SSID:

`SSID:123456`

After the SSID is set, emit a message that sets the WiFi password:

`PSWD:123456`

If the password is empty, the plugin treats the network as open:

`PSWD:`

Once the password is received, the plugin sends a bus message for [ovos-PHAL-plugin-network-manager](https://github.com/OpenVoiceOS/ovos-PHAL-plugin-network-manager) to handle.

### Install a GitHub skill

Install a skill from a GitHub URL:

`GHS:https://github.com/OpenVoiceOS/skill-ovos-icanhazdadjokes`

### Install a Python package

Install any package from PyPI:

`PIP:skill-wikipedia-for-humans`

### Utterance

Inject an utterance into the messagebus, as if the user spoke it to the microphone:

`UTT:hello cruel world`

### Speak

Make an OVOS device speak:

`SPEAK:hello world`

### Bus

Inject a simple message into the messagebus:

`BUS:recognizer_loop:sleep`

### JSON

Inject a serialized message into the messagebus:

`JSON:{"type": "speak", "data": {"utterance": "hello"}, "context": {}}`

## Related projects

- [OpenVoiceOS/ovos-skill-ggwave](https://github.com/OpenVoiceOS/ovos-skill-ggwave) — voice control for this plugin
- [OpenVoiceOS/ovos-PHAL-plugin-network-manager](https://github.com/OpenVoiceOS/ovos-PHAL-plugin-network-manager) — handles WiFi setup messages sent by this plugin
- [OpenVoiceOS/ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener) — listener service that can load this plugin
