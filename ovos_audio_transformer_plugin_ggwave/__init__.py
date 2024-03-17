import datetime

from ovos_workshop.skills.ovos import OVOSSkill
from ovos_workshop.decorators import intent_handler



class GGWaveSkill(OVOSSkill):

    def initialize(self):
        self.add_event("ggwave.enabled", self.handle_ggwave_on)
        self.add_event("ggwave.disabled", self.handle_ggwave_off)
        self.enabled = False

    def handle_ggwave_on(self, message):
        self.enabled = True
        self.schedule_event(
            handler=self.handle_ggwave_off,
            when=datetime.datetime.now() + datetime.timedelta(minutes=15),
            name="ggwave.timeout"
        )

    def handle_ggwave_off(self, message):
        self.enabled = False

    @intent_handler("enable.ggwave.intent")
    def handle_enable_ggwave(self, message):
        if not self.enabled:
            self.bus.emit(message.forward("ovos.ggwave.enable"))
            self.speak_dialog("ggwave.enabled")
        else:
            self.speak_dialog("ggwave.already.enabled")

    @intent_handler("disable.ggwave.intent")
    def handle_disable_ggwave(self, message):
        if self.enabled:
            self.bus.emit(message.forward("ovos.ggwave.disable"))
            self.cancel_scheduled_event("ggwave.timeout")
            self.speak_dialog("ggwave.disabled")
        else:
            self.speak_dialog("ggwave.already.disabled")

