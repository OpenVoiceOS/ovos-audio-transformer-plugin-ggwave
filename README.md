# GGWave audio plugin

plugin for https://github.com/ggerganov/ggwave

you need the ggwave-rx binary available, then you can emit special messages to be handled by this plugin via sound

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


### Bus

inject a simple message in the messagebus

`BUS:recognizer_loop:sleep`

### Utterance

inject an utterance in the messagebus like if the user spoke it to the microphone

`UTT:hello cruel world`

### Wifi setup

emit a message setting the wifi SSID
`SSID:123456`

after the SSID is set, emit a message setting the wifi password
`PSWD:123456`

if password is empty then it is assumed to be an open network
`PSWD:`

once password is received a bus message is sent for [ovos-PHAL-plugin-network-manager](https://github.com/OpenVoiceOS/ovos-PHAL-plugin-network-manager) to handle
