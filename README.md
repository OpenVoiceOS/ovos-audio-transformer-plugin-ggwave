# GGWave audio plugin

plugin for https://github.com/ggerganov/ggwave

you need the ggwave-rx binary available, then you can emit special messages to be handled by this plugin via sound

To setup WiFI on OpenVoiceOS devices go to https://openvoiceos.github.io/ovos-audio-transformer-plugin-ggwave/


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

WIP - needs https://github.com/OpenVoiceOS/ovos-core/pull/347/

install a skill from a github url

`GHS:https://github.com/OpenVoiceOS/skill-ovos-icanhazdadjokes`

### Install a python package

WIP - needs https://github.com/OpenVoiceOS/ovos-core/pull/347/

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


