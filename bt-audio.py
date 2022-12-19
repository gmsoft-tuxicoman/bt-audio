#!/usr/bin/python3

import dbus
import dbus.service
import dbus.mainloop.glib
import logging

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst

import argparse

argparser = argparse.ArgumentParser(description='Send bluetooth audio to alsa card')
argparser.add_argument('--alsa-device', '-D', dest='alsadev', help='Alsa device')
argparser.add_argument('--adapter', '-a', dest='adapter', help='Bluetooth adapter', default='hci0')
argparser.add_argument('--buffer-length', '-b', dest='buff_len', help='Length of the jitter buffer', default=50)
argparser.add_argument('--aac', '-A', dest='aac_enabled', help='Enable AAC codec support', default=False, action='store_true')
argparser.add_argument('--debug', '-d', dest='debug', help='Enable debugging', default=False, action='store_const', const=True)

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

A2DP_SINK_UUID = "0000110b-0000-1000-8000-00805f9B34fb"
A2DP_SERVICE_UUID = "0000110d-0000-1000-8000-00805f9b34fb"
SBC_CODEC = dbus.Byte(0x00)
SBC_CAPABILITIES = dbus.Array([dbus.Byte(0xff), dbus.Byte(0xff), dbus.Byte(2), dbus.Byte(64)])

AAC_CODEC = dbus.Byte(0x02)
AAC_CAPABILITIES = dbus.Array([dbus.Byte(0xC0), dbus.Byte(0xFF), dbus.Byte(0xFC), dbus.Byte(0xFF), dbus.Byte(0xFF), dbus.Byte(0xFF)])
#AAC_CAPABILITIES = dbus.Array([dbus.Byte(0x80), dbus.Byte(0xFF), dbus.Byte(0xFC), dbus.Byte(0xFF), dbus.Byte(0xFF), dbus.Byte(0xFF)])



class Bluez():
    
    def __init__(self):

        self.bus = dbus.SystemBus()
        self.adapters = {}

        self.logger = logging.getLogger("Bluez")


        self.bus.add_signal_receiver(self._interfaceAdded, dbus_interface='org.freedesktop.DBus.ObjectManager', signal_name = "InterfacesAdded")
        self.bus.add_signal_receiver(self._interfaceRemoved, dbus_interface='org.freedesktop.DBus.ObjectManager', signal_name = "InterfacesRemoved")
        self.bus.add_signal_receiver(self._propertiesChanged, dbus_interface='org.freedesktop.DBus.Properties', signal_name = "PropertiesChanged", path_keyword = "path")

        # Find the adapters and create the objects
        obj_mgr = dbus.Interface(self.bus.get_object("org.bluez", "/"), 'org.freedesktop.DBus.ObjectManager')
        objs = obj_mgr.GetManagedObjects()
        for obj_path in objs:
            obj = objs[obj_path]
            if 'org.bluez.Adapter1' in obj:
                adapt_name = obj_path.split('/')[3]
                self.adapters[adapt_name] = Adapter(self.bus, obj_path)
                self.adapters[adapt_name].agentRegister()
               
    def _interfaceAdded(self, path, interface):
        self.logger.debug(path + " | " + str(interface))
        adapt_name = path.split('/')[3]
        if 'org.bluez.Adapter1' in interface:
            self.adapters[adapt_name] = Adapter(self.bus, path)
            self.adapters[adapt_name].agentRegister()
        elif adapt_name in self.adapters:
            self.adapters[adapt_name]._interfaceAdded(path, interface)
                
    def _interfaceRemoved(self, path, interface):
        self.logger.debug(path + " | " + str(interface))
        spath = path.split('/')
        if len(spath) < 4:
            return
        adapt_name = spath[3]
        if 'rg.bluez.Adapter1' in interface:
            del self.adapters[adapt_name]
        elif adapt_name in self.adapters:
            self.adapters[adapt_name]._interfaceRemoved(path, interface)

    def _propertiesChanged(self, interface, changed, invalidated, path):
        if not path.startswith("/org/bluez/"):
            return

        self.logger.debug(path + " | " + str(interface) + " | " + str(changed) + " | " + str(invalidated))

        adapt_name = path.split('/')[3]
        if adapt_name in self.adapters:
            self.adapters[adapt_name]._propertiesChanged(interface, changed, invalidated, path)

    def getAdapter(self, adapt_name):
        if adapt_name in self.adapters:
            return self.adapters[adapt_name]
        return None


class Adapter():

    def __init__(self, bus, path):


        self.logger = logging.getLogger("Adapter")

        self.logger.info("New adapter " + path)
        self.bus = bus
        self.path = path
        self.prop = dbus.Interface(self.bus.get_object("org.bluez", path), "org.freedesktop.DBus.Properties")
        self.devices = {}

        obj_mgr = dbus.Interface(self.bus.get_object("org.bluez", "/"), 'org.freedesktop.DBus.ObjectManager')
        objs = obj_mgr.GetManagedObjects()
        for obj_path in objs:
            obj = objs[obj_path]
            if 'org.bluez.Device1' in obj:
                dev_name = obj_path.split('/')[4]
                self.devices[dev_name] = Device(self.bus, obj_path)

    def __del__(self):
        self.logger.info("Removed adapter " + self.path)

    def _interfaceAdded(self, path, interface):
        self.logger.debug(path)
        spath = path.split('/')
        dev_name = spath[4]
        if 'org.bluez.Device1' in interface:
            self.devices[dev_name] = Device(self.bus, path)
        elif dev_name in self.devices and len(spath) > 5:
            self.devices[dev_name]._interfaceAdded(path, interface)
        
    def _interfaceRemoved(self, path, interface):
        self.logger.debug(path)
        spath = path.split('/')
        if len(spath) < 5:
            return
        dev_name = spath[4]
        if 'org.bluez.Device1' in interface:
            del self.devices[dev_name]
        elif dev_name in self.devices:
            self.devices[dev_name]._interfaceRemoved(path, interface)

    def _propertiesChanged(self, interface, changed, invalidated, path):
        self.logger.debug(path)
        spath = path.split('/')
        if len(spath) >= 5:
            dev_name  = spath[4]
            if dev_name in self.devices:
                self.devices[dev_name]._propertiesChanged(interface, changed, invalidated, path)
            return

        # Handle out property change here
        
    def powerSet(self, status):
        self.logger.info("Turning on adapter " + self.path)
        self.prop.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(status))

    def discoverableSet(self, status):
        self.logger.info("Making adapter " + self.path + " discoverable")
        self.prop.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(status))

    def mediaEndpointRegisterSBC(self):
        media = dbus.Interface(self.bus.get_object("org.bluez", self.path), "org.bluez.Media1")
        media_path = '/test/endpoint_sbc_' + self.path.split('/')[3]
        self.mediaEndpointSBC = MediaEndpoint(self.bus, media_path)
        properties = dbus.Dictionary({ "UUID" : A2DP_SINK_UUID, "Codec" : SBC_CODEC, "DelayReporting" : True, "Capabilities" : SBC_CAPABILITIES })
        media.RegisterEndpoint(media_path, properties)
        self.logger.info("MediaEndpoint SBC registered for " + self.path)

    def mediaEndpointRegisterAAC(self):
        media = dbus.Interface(self.bus.get_object("org.bluez", self.path), "org.bluez.Media1")
        media_path = '/test/endpoint_aac_' + self.path.split('/')[3]
        self.mediaEndpointAAC = MediaEndpoint(self.bus, media_path)
        properties = dbus.Dictionary({ "UUID" : A2DP_SINK_UUID, "Codec" : AAC_CODEC, "DelayReporting" : True, "Capabilities" : AAC_CAPABILITIES })
        media.RegisterEndpoint(media_path, properties)
        self.logger.info("MediaEndpoint AAC registered for " + self.path)

    def agentRegister(self):
        agent_path = '/test/agent_' + self.path.split('/')[3]
        self.agent = Agent(self.bus, agent_path)

        manager = dbus.Interface(self.bus.get_object("org.bluez", "/org/bluez"), "org.bluez.AgentManager1")
        manager.RegisterAgent(agent_path, "NoInputNoOutput")

        manager.RequestDefaultAgent(agent_path)

class Device():

    def __init__(self, bus, path):
        self.logger = logging.getLogger("Device")
        self.bus = bus
        self.path = path
        self.mediaTransports = {}

    def __del__(self):
        self.logger.info("Removed device " + self.path)

    def _interfaceAdded(self, path, interface):
        self.logger.debug(path)
        spath = path.split('/')
        if len(spath) < 6:
            return
        obj_name = spath[5]
        if 'org.bluez.MediaTransport1' in interface:
            mediaTransport1 = interface['org.bluez.MediaTransport1']
            if mediaTransport1['Codec'] == SBC_CODEC:
                self.mediaTransports[obj_name] = MediaTransportSBC(self.bus, path)
            elif mediaTransport1['Codec'] == AAC_CODEC:
                self.mediaTransports[obj_name] = MediaTransportAAC(self.bus, path)
            else:
                self.logger.warn("Unsupported codec : " + str(mediaTransport1['Codec']))

    def _interfaceRemoved(self, path, interface):
        self.logger.debug(path)
        obj_name = path.split('/')[5]
        self.logger.debug("Removing media transport " + obj_name)
        if 'org.bluez.MediaTransport1' in interface and obj_name in self.mediaTransports:
            self.mediaTransports[obj_name]._interfaceRemoved(path, interface)
            del self.mediaTransports[obj_name]

    def _propertiesChanged(self, interface, changed, invalidated, path):
        self.logger.debug(path)
        spath = path.split('/')

        if len(spath) == 5 and "Connected" in changed and "org.bluez.Device1" in interface:
            if changed["Connected"]:
                self.logger.info("Device " + spath[4] + " connected")
            else:
                self.logger.info("Device " + spath[4] + " disconnected")

        if len(spath) >= 6:
            obj_name = spath[5]
            if 'org.bluez.MediaTransport1' in interface and obj_name in self.mediaTransports:
                self.mediaTransports[obj_name]._propertiesChanged(interface, changed, invalidated, path)

class MediaEndpoint(dbus.service.Object):

    def __init__(self, bus, path):
        self.bus = bus
        self.path = path
        super(MediaEndpoint, self).__init__(bus, path)

    @dbus.service.method("org.bluez.MediaEndpoint1", in_signature="ay", out_signature="ay")
    def SelectConfiguration(self, caps):
        if args.debug:
            print("MediaEndpoint | SelectConfiguration (%s)" % (caps))
        return self.configuration

    @dbus.service.method("org.bluez.MediaEndpoint1", in_signature="oay", out_signature="")
    def SetConfiguration(self, transport, config):
        if args.debug:
            print("MediaEndpoint | SetConfiguration (%s, %s)" % (transport, config))

    @dbus.service.method("org.bluez.MediaEndpoint1", in_signature="o", out_signature="")
    def ClearConfiguration(self, transport):
        if args.debug:
            print("MediaEndpoint | ClearConfiguration (%s)" % (transport))

    @dbus.service.method("org.bluez.MediaEndpoint1", in_signature="", out_signature="")
    def Release(self):
        if args.debug:
            print("MediaEndpoint | Release")

class MediaTransport():

    def __init__(self, bus, path):
        self.bus = bus
        self.path = path
        self.pipeline = None
        self.logger = logging.getLogger("MediaTransport")

    def _propertiesChanged(self, interface, changed, invalidated, path):
        self.logger.debug(path)

        if not 'State' in changed:
            return

        newState = changed['State']
        if newState == 'pending':
            if not self.pipeline:
                self.initPipeline()

            self.pipeline.set_state(Gst.State.PLAYING)
            self.logger.info("Playback started !")

        elif newState == 'idle':
            if not self.pipeline:
                return
            self.pipeline.set_state(Gst.State.NULL)
            self.logger.info("Playback stopped !")


    def _interfaceRemoved(self, path, interface):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

    def _gst_on_message(self, gst_bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            self.logger.error(str(err) + " " + str(debug))
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            self.logger.warning(str(err) + " " + str(debug))
        else:
            self.logger.debug(str(message.type) + " " + str(message.src))

class MediaTransportSBC(MediaTransport):


    def __init__(self, bus, path):
        super().__init__(bus, path)
        self.logger = logging.getLogger("MediaTransportSBC")

    def initPipeline(self):

        global args

        self.pipeline = Gst.Pipeline.new("player")

        gst_bus = self.pipeline.get_bus()
        gst_bus.add_signal_watch()
        gst_bus.connect("message", self._gst_on_message)

        source = Gst.ElementFactory.make("avdtpsrc", "bluetooth-source")
        source.set_property("transport", self.path)

        jitterbuffer = Gst.ElementFactory.make("rtpjitterbuffer", "jitterbuffer")
        jitterbuffer.set_property("latency", args.buff_len)
        jitterbuffer.set_property("drop-on-latency", "true")

        depay = Gst.ElementFactory.make("rtpsbcdepay", "depayloader")

        parse = Gst.ElementFactory.make("sbcparse", "parser")

        decoder = Gst.ElementFactory.make("sbcdec", "decoder")

        converter = Gst.ElementFactory.make("audioconvert", "converter")

        sink = Gst.ElementFactory.make("alsasink", "alsa-output")
        if args.alsadev:
            sink.set_property("device", args.alsadev)

        self.pipeline.add(source)
        self.pipeline.add(jitterbuffer)
        self.pipeline.add(depay)
        self.pipeline.add(parse)
        self.pipeline.add(decoder)
        self.pipeline.add(converter)
        self.pipeline.add(sink)


        link = True
        link &= source.link(jitterbuffer)
        link &= jitterbuffer.link(depay)
        link &= depay.link(parse)
        link &= parse.link(decoder)
        link &= decoder.link(converter)
        link &= converter.link(sink)

        if not link:
            self.logger.critical("Failed to link the pipeline")
            return

        self.logger.debug("Created new SBC pipeline")



class MediaTransportAAC(MediaTransport):

    def __init__(self, bus, path):
        super().__init__(bus, path)
        self.logger = logging.getLogger("MediaTransportAAC")

    def initPipeline(self):
        global args

        self.pipeline = Gst.Pipeline.new("player")

        gst_bus = self.pipeline.get_bus()
        gst_bus.add_signal_watch()
        gst_bus.connect("message", self._gst_on_message)

        source = Gst.ElementFactory.make("avdtpsrc", "bluetooth-source")
        source.set_property("transport", self.path)

        jitterbuffer = Gst.ElementFactory.make("rtpjitterbuffer", "jitterbuffer")
        jitterbuffer.set_property("latency", args.buff_len)
        jitterbuffer.set_property("drop-on-latency", "true")

        depay = Gst.ElementFactory.make("rtpmp4adepay", "depayloader")

        decoder = Gst.ElementFactory.make("faad", "decoder")

        converter = Gst.ElementFactory.make("audioconvert", "converter")

        sink = Gst.ElementFactory.make("alsasink", "alsa-output")
        if args.alsadev:
            sink.set_property("device", args.alsadev)

        self.pipeline.add(source)
        self.pipeline.add(jitterbuffer)
        self.pipeline.add(depay)
        self.pipeline.add(decoder)
        self.pipeline.add(converter)
        self.pipeline.add(sink)

        link = True
        link &= source.link(jitterbuffer)
        link &= jitterbuffer.link(depay)
        link &= depay.link(decoder)
        link &= decoder.link(converter)
        link &= converter.link(sink)

        if not link:
            self.logger.crit("Failed to link the pipeline")
            return


        self.logger.debug("Created new AAC pipeline")


class Rejected(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Rejected"

class Agent(dbus.service.Object):

    @dbus.service.method('org.bluez.Agent1', in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        if (uuid != A2DP_SERVICE_UUID):
            raise Rejected("Service unauthorized")


def sanity_checks():

    if not hasattr(Gst._overrides_module, "ElementFactory"):
        raise Exception("gst=python module does not seem to be installed")

    pipeline = Gst.Pipeline.new("sanity_check")
    if not pipeline:
        raise Exception("Cannot create Gstreamer pipeline")

    gst_plugins = [ "avdtpsrc", "rtpjitterbuffer", "rtpsbcdepay", "sbcparse", "sbcdec", "audioconvert", "alsasink" ]

    for plugin in gst_plugins:
        if not Gst.ElementFactory.find(plugin):
            raise Exception("Gstreamer plugin " + plugin + " not found !")


def main():

    global args
    args = argparser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(name)s:%(funcName)s:%(message)s")
    else:
        logging.basicConfig(level=logging.INFO)

    # Init Gstreamer and check we have all the required plugins
    Gst.init(None)
    sanity_checks()

    # Init bluetooth stuff
    bluez = Bluez()
    adapt = bluez.getAdapter(args.adapter)

    if not adapt:
        print("Adapter " + args.adapter + " not found")
        return

    # Setup our BT adapter
    adapt.powerSet(True)
    adapt.discoverableSet(True)
    adapt.mediaEndpointRegisterSBC()


    if args.aac_enabled:
        adapt.mediaEndpointRegisterAAC()


    # Glib main loop
    mainloop = GLib.MainLoop()
    mainloop.run()
    return


if __name__ == '__main__':
    main()
