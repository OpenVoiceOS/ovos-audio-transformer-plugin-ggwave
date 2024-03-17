# GGWave audio plugin

plugin for https://github.com/ggerganov/ggwave

Emit audio QR codes to be handled by this plugin

Interact with this plugin from your [browser](https://openvoiceos.github.io/ovos-audio-transformer-plugin-ggwave/), including WiFi setup

The companion skill [OpenVoiceOS/ovos-skill-ggwave](https://github.com/OpenVoiceOS/ovos-skill-ggwave) allows you to enable/disable this plugin by voice

Skill stores support installing skills via GGWave:
- [OVOS-skills-store](https://openvoiceos.github.io/OVOS-skills-store)
- [OVOS-Hatchery-skills](https://ovoshatchery.github.io/OVOS-Hatchery-skills)
  
```javascript
"skills": {
    "installer": {
      "allow_pip": true,
      "allow_alphas": true,
      "break_system_packages": false
    }
}
```
> **TIP** Allow ovos-core to install python packages, otherwise the install commands from this plugin will error out

## Install

`pip install ovos-audio-transformer-plugin-ggwave`

> ggwave [fails to install on python 3.11](https://github.com/ggerganov/ggwave/issues/89), you can use the wheel from here https://whl.smartgic.io/ , plugin install should then work

## Listener Plugin

To have this plugin loaded by dinkum-listener, enable it in mycroft.conf

> **WARNING** currently not recommended, see [bug report in dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener/issues/98)

```javascript
"listener": {
    "audio_transformers": {
        "ovos-audio-transformer-plugin-ggwave": {
            "start_enabled": true
        }
    }
}
```

## Standalone

You can also run the plugin in standalone mode, in it's own process or docker container

Launch with the console entrypoint
```bash
ovos-ggwave-listener
```

## Valid Audio Data

this repo provides a test interface via [github pages](https://openvoiceos.github.io/ovos-audio-transformer-plugin-ggwave/)

you can also test your own payloads via https://ggwave-js.ggerganov.com/ 

### Wifi setup

emit a message setting the wifi SSID
`SSID:123456`

after the SSID is set, emit a message setting the wifi password
`PSWD:123456`

if password is empty then it is assumed to be an open network
`PSWD:`

once password is received a bus message is sent for [ovos-PHAL-plugin-network-manager](https://github.com/OpenVoiceOS/ovos-PHAL-plugin-network-manager) to handle

### Install a github skill

install a skill from a github url

`GHS:https://github.com/OpenVoiceOS/skill-ovos-icanhazdadjokes`

### Install a python package

install any package from pypi

`PIP:skill-wikipedia-for-humans`

### Utterance

inject an utterance in the messagebus like if the user spoke it to the microphone

`UTT:hello cruel world`

### Speak

make a OVOS device speak

`SPEAK:hello world`

### Bus

inject a simple message in the messagebus

`BUS:recognizer_loop:sleep`

### Json

inject a serialized message in the messagebus

`JSON:{"type": "speak", "data": {"utterance": "hello"}, "context": {}}`


