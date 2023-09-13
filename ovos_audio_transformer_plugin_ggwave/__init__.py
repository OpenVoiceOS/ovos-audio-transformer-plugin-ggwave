from os.path import isfile, expanduser

import pexpect
from ovos_plugin_manager.templates.transformers import AudioTransformer
from ovos_utils import create_daemon
from ovos_utils.log import LOG
from ovos_utils.messagebus import Message, get_mycroft_bus


# NOTE - could not get ggwave to work properly with the audio feed
# ran out of time so just used a subprocess
class GGWavePlugin(AudioTransformer):

    def __init__(self, config=None):
        config = config or {}
        super().__init__("ovos-audio-transformer-plugin-ggwave", 10, config)
        self.binpath = self.config.get("binary") or expanduser("~/.local/bin/ggwave-rx")
        if not isfile(self.binpath):
            raise ValueError(f"ggwave-rx not found in {self.binpath}, "
                             f"please install from https://github.com/ggerganov/ggwave")
        self.OPCODES = {
            "SSID:": self.handle_wifi_ssid,
            "PSWD:": self.handle_wifi_pswd,
            "UTT:": self.handle_utt,
            "BUS:": self.handle_bus
        }
        # TODO - allow passing bus to plugins instead of creating new connection
        self.bus = get_mycroft_bus()
        self.daemon = create_daemon(self.monitor_thread)

        self._ssid = None

    def handle_bus(self, payload):
        LOG.info(f"bus msg_type: {payload}")
        self.bus.emit(Message(payload))

    def handle_utt(self, payload):
        LOG.info(f"Utterance: {payload}")
        self.bus.emit(Message("recognizer_loop:utterance",
                              {"utterances": [payload]}))

    def handle_wifi_ssid(self, payload):
        LOG.info(f"Wifi AP: {payload}")
        self._ssid = payload

    def handle_wifi_pswd(self, payload):
        if not self._ssid:
            LOG.error("received wifi password but wifi SSID not set! ignoring")
            return

        if not payload:
            LOG.info("wifi is open, no password")
            data = {"connection_name": self._ssid}
            self.bus.emit(Message("ovos.phal.nm.connect.open.network", data))
        else:
            LOG.info(f"Wifi PSWD {payload}")
            data = {"connection_name": self._ssid, "password": payload}
            self.bus.emit(Message("ovos.phal.nm.connect", data))

        self._ssid = None

    def monitor_thread(self):
        child = pexpect.spawn(self.binpath)
        marker = "Received sound data successfully: "
        while True:
            try:
                txt = child.readline().decode("utf-8").strip()
                if txt.startswith(marker):
                    payload = txt.split(marker)[-1][1:-1]
                    for opcode, handler in self.OPCODES.items():
                        if payload.startswith(opcode):
                            p = payload.split(opcode, 1)[-1]
                            handler(p)
                            break
                    else:
                        print(f"invalid ggwave payload: {payload}")
            except pexpect.exceptions.EOF:
                # exited
                print("Exited ggwave-rx process")
                break
            except pexpect.exceptions.TIMEOUT:
                # nothing happened for a while
                pass
            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    from ovos_utils import wait_for_exit_signal

    binary = "/home/miro/PycharmProjects/ovos-audio-transformer-plugin-ggwave/ggwave/build/bin/ggwave-rx"

    gg = GGWavePlugin({"binary": binary})

    wait_for_exit_signal()
