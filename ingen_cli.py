#!/usr/bin/env python2

from ingen import Remote
from cmd2 import Cmd

import readline, sys, socket, lilv, rdflib, pyparsing

INSTANCE_PREFIX = "effect_"
readline.set_completer_delims(' ')

class IngenCLI(Cmd, object):

    prompt = "ingen-cli> "
    commentGrammars = pyparsing.cStyleComment

    def __init__(self, *args, **kwargs):
        self.world = lilv.World()
        self.world.load_all()
        self._known_plugins = []

        for plugin in self.world.get_all_plugins():
            self._known_plugins.append(plugin)

        try:
            self.ingen = Remote()
        except socket.error:
            print "Can't connect to Ingen"
            sys.exit(1)

        Cmd.__init__(self, *args, **kwargs)

    def _instance_ids(self):
        graph = self.ingen.get("/")
        ids = []
        # get all blocks
        for block in graph.subjects(object=rdflib.term.URIRef(u'http://drobilla.net/ns/ingen#Block')):
            subj = list(graph.subjects(object=block))[0]
            uri = list(graph.objects(subject=subj, predicate=rdflib.term.URIRef(u'http://lv2plug.in/ns/ext/patch#subject')))[0]
            if INSTANCE_PREFIX in uri.toPython():
                ids.append(uri.toPython().split(INSTANCE_PREFIX)[-1])
        return ids

    def _get_instance_control_ports(self, instance_id):
        graph = self.ingen.get("/%s%s" % (INSTANCE_PREFIX, instance_id))
        ports = []
        for subject in graph.subjects(object=rdflib.term.URIRef(u'http://lv2plug.in/ns/lv2core#ControlPort')):
            obj = list(graph.subjects(object=subject))[0]
            ports.append(list(graph.objects(subject=obj, predicate=rdflib.term.URIRef(u'http://lv2plug.in/ns/ext/patch#subject')))[0])
        return [ port.toPython().split("/")[-1] for port in ports ]

    def do_add(self, args):
        plugin_uri, instance_id = args.split()
        self.ingen.put("/%s%s" % (INSTANCE_PREFIX, instance_id), "a ingen:Block ; ingen:prototype <%s>" % (plugin_uri))

    def complete_add(self, text, line, begidx, endidx):
        return [ plugin.get_uri().as_string() for plugin in self._known_plugins if plugin.get_uri().as_string().startswith(text) ]

    def do_remove(self, instance_id):
        r = self.ingen.delete("/%s%s" % (INSTANCE_PREFIX, instance_id))

    def do_preset(self, args):
        instance_id, preset = args.split()
        preset = "<%s>" % preset
        self.ingen.set("/%s%s" % (INSTANCE_PREFIX, instance_id), "<http://lv2plug.in/ns/ext/presets#preset>", preset)

    def do_save_preset(self):
        pass

    def do_connect(self, args):
        port_a, port_b = args.split()
        self.ingen.connect(port_a, port_b)

    def complete_connect(self, text, line, begidx, endidx):
        if len(line.split()) > 3:
            return []

        graph = self.ingen.get("/")
        ports = []

        if (len(line.split()) == 1 and not text) or (len(line.split()) == 2 and text):
            # output ports
            ports = graph.subjects(object=rdflib.term.URIRef(u'http://lv2plug.in/ns/lv2core#OutputPort'))

        elif (len(line.split()) == 2 and not text) or (len(line.split()) == 3 and text):
            # input ports
            ports = graph.subjects(object=rdflib.term.URIRef(u'http://lv2plug.in/ns/lv2core#InputPort'))

        objs =[]
        for output in ports:
            for subject in graph.subjects(object=output):
                objs += list(graph.objects(predicate=rdflib.term.URIRef(u"http://lv2plug.in/ns/ext/patch#subject"),subject=subject))
        return [ v.toPython().split(self.ingen.server_base[:-1])[1]
                for v in objs
                  if v.toPython().split(self.ingen.server_base[:-1])[1].startswith(text) ]

    def do_disconnect(self, args):
        port_a, port_b = args.split()
        self.ingen.disconnect(port_a, port_b)

    def complete_disconnect(self, text, line, begidx, endidx):
        if len(line.split()) > 3:
            return []
        graph = self.ingen.get("/")
        arcs = graph.subjects(object=rdflib.term.URIRef(u'http://drobilla.net/ns/ingen#Arc'))
        if (len(line.split()) == 1 and not text) or (len(line.split()) == 2 and text):
            for arc in arcs:
                return [ tail.toPython().split(self.ingen.server_base[:-1])[1]
                         for tail in graph.objects(subject=arc, predicate=rdflib.term.URIRef(u'http://drobilla.net/ns/ingen#tail'))
                           if tail.toPython().split(self.ingen.server_base[:-1])[1].startswith(text) ]

        elif (len(line.split()) == 2 and not text) or (len(line.split()) == 3 and text):
            heads = []
            for arc in arcs:
                for head in graph.objects(subject=arc, predicate=rdflib.term.URIRef(u'http://drobilla.net/ns/ingen#head')):
                    h = head.toPython().split(self.ingen.server_base[:-1])[1]
                    if h.startswith(text):
                        tails = graph.objects(subject=arc, predicate=rdflib.term.URIRef(u'http://drobilla.net/ns/ingen#tail'))
                        if line.split()[1] in [ tail.toPython().split(self.ingen.server_base[:-1])[1] for tail in tails ]:
                            heads.append(h)
            return heads
        return []

    def do_bypass(self, args):
        instance_id, value = args.split()
        # if bypass = 0 ; enabled = true
        if value == "0":
            value = "true"
        else:
            value = "false"
        self.ingen.set("/%s%s" % (INSTANCE_PREFIX, instance_id), "ingen:enabled", value)

    def do_param_set(self, args):
        instance_id, port_symbol, value = args.split()
        value = float(value)
        r = self.ingen.set( "/%s%s/%s" % (INSTANCE_PREFIX, instance_id, port_symbol),
                "ingen:value", value)

    def complete_param_set(self, text, line, begidx, endidx):
        if len(line.split()) == 1 and not text or len(line.split()) == 2 and text:
            return [ instance_id for instance_id in self._instance_ids() if instance_id.startswith(text)]

        elif len(line.split()) == 2 and not text or len(line.split()) == 3 and text:
            return [ port for port in self._get_instance_control_ports(line.split()[1]) if port.startswith(text) ]

        return []

    def do_param_get(self, args):
        instance_id, port_symbol = args.split()
        r = self.ingen.get("/%s%s/%s" % (INSTANCE_PREFIX, instance_id, port_symbol))
        obj = r.objects(predicate=rdflib.term.URIRef(u'http://drobilla.net/ns/ingen#value'))
        try:
            print obj.next().toPython()
        except StopIteration:
            print "Invalid port or instance"

    def complete_param_get(self, text, line, begidx, endidx):
        # same as param_set
        return self.complete_param_set(text, line, begidx, endidx)

    def help(self):
        pass

if __name__ == "__main__":
    cli = IngenCLI()
    cli.cmdloop()
