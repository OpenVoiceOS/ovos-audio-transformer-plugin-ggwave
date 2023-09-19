# GGWave audio plugin

plugin for https://github.com/ggerganov/ggwave

Emit audio QR codes to be handled by this plugin

To setup WiFI on OpenVoiceOS devices go to https://openvoiceos.github.io/ovos-audio-transformer-plugin-ggwave/

## Install ggwave

you need the ggwave-rx binary available, setup.py will attempt to compile it automatically for you

manual setup
```bash
#!/bin/bash
git clone https://github.com/ggerganov/ggwave --recursive /tmp/ggwave
cd /tmp/ggwave && mkdir /tmp/ggwave/build && cd /tmp/ggwave/build
cmake .. && make

mv /tmp/ggwave/build/bin/* $HOME/.local/bin/
rm -rf /tmp/ggwave
```

## config

enable the plugin in mycroft.conf

```javascript
"listener": {
    "audio_transformers": {
        "ovos-audio-transformer-plugin-ggwave": {
            "binary": "~/.local/bin/ggwave-rx"
        }
    }
}
```

## Valid messages

the easiest way to test is by using https://ggwave-js.ggerganov.com/ to send audio payloads

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


