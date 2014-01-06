# -*- coding: utf-8 -*
#
# Copyright 2014 Rickard Petzäll

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""XML-RPC over pipe transport (for SSH)

Example (client):
-----------------

    proc = subprocess.Popen(["ssh","myserver","python", "server.py"], 
       stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    
    rpc = piperpclib.ServerProxy(process=proc, path=path)
    rpc.my_method("Some","Args")

Example (server):
-----------------

    def my_method(arg1, arg2):
       ...
    
    rpc = piperpclib.Server()
    rpc.register_function(my_method)
    rpc.serve_forever()
"""
#from __future__ import print_function
import sys, os
import traceback
try:
    import xmlrpclib
    __OLDSTYLE_XMLRPC_PACKAGES = True
except ImportError:
    __OLDSTYLE_XMLRPC_PACKAGES = False
    
if __OLDSTYLE_XMLRPC_PACKAGES:
    from xmlrpclib import Fault
    from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCDispatcher
    BUF = lambda _:_
else:
    from xmlrpc.client import Fault
    import xmlrpc.client as xmlrpclib
    from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCDispatcher
    BUF = lambda s:bytes(s,'UTF-8')

__ALL__ = ["Server", "ServerProxy", "PipeTransport", "Fault", "SimpleXMLRPCDispatcher"]


class PipeTransport:
    input = None
    output = None
    tagname = "Client"
    timeout=10
    
    def __init__(self, input, output, use_datetime=0):
        if not input or not output:
            raise ValueError("Both input and output are mandatory")
        self.input = input
        self.output = output
        self.use_datetime = use_datetime
        
        
    def request(self, host, handler, request_body, verbose=0):
        try:
            self.write_item(handler, request_body)
            return self.parse_response(handler)
        except xmlrpclib.Fault:
            #print("%s: Received fault" % self.tagname, file=sys.stderr)
            raise
        except Exception:
            #print("%s: Received exception" % self.tagname, file=sys.stderr)
            # All unexpected errors leave connection in
            # a strange state, so we clear it.
            self.close()
            raise
            
    def read_item(self):
        #print("%s: Awaiting another item" % self.tagname, file=sys.stderr)
        if self.timeout:
            # TODO: Use select() as the platform-independent way of waiting for a fh
            pass
        ln = []
        while True:
            c = self.input.read(1)
            if len(c) == 0:
                ln = []
                break
            if c == '\n':
                break
            ln.append(c)
        ln = ''.join(ln)
        if not ln:
            self.close()
            ioe = IOError("Unexpected end of stream")
            ioe.errno = 32
            raise ioe
        rpc,ver,h,datalen = ln.split(" ")
       # print("%s: Received RPC %r" % (self.tagname, (rpc,ver,h,datalen)), file=sys.stderr)
        if rpc != "RPC":
            raise xmlrpclib.ResponseError("Other end is not piperpc (%s)" % ln)
        if not ver.isdigit() or int(ver) != 1 or not datalen.isdigit():
            raise xmlrpclib.ResponseError("Unsupported piperpc version")
        
        datalen = int(datalen)
        data = self.input.read(datalen)
        return h, data
        
    def write_item(self, handler, request_body):
        self.output.write(BUF("RPC 1 %s %d\n" % (handler, len(request_body))))
        self.output.write(request_body)
        self.output.flush()
        
    def parse_response(self, handler):
        #print("%s: Receiving data" % self.tagname, file=sys.stderr)
        h, data = self.read_item()
        #print("%s: Received data" % self.tagname, file=sys.stderr)
        if h != handler:
            raise xmlrpclib.ResponseError("RPC handlers mismatch, %s != %s" % (h, handler))
                    
        p, u = xmlrpclib.getparser(self.use_datetime)
        p.feed(data)
        p.close()
        return u.close()
            
    def close_file(self, file):
        # Never close stdin or stderr, but close stdout to signify EOF if necessary
        if file and (sys is None or not file in (sys.stdin, sys.stderr)):
            file.close()
    
    def close(self):
        self.close_file(self.input)
        self.close_file(self.output)
        
    def __del__(self):
        self.close()
    
class ServerProxy(xmlrpclib.ServerProxy):    
    def __init__(self, input=None, output=None, process=None, path="/RPC2"):
        if process:
            if input or output:
                raise ValueError("Parameters input, output are mutually exclusive with process")
            input = process.stdout
            output = process.stdin
            if not input or not output:
                raise ValueError("Process must be started with stdin=subprocess.PIPE and stdout=subprocess.PIPE")
        if not input:
            raise ValueError("Input was not set")
        if not output:
            raise ValueError("Output was not set")
        if path[0] != "/": path = "/%s" % path
        xmlrpclib.ServerProxy.__init__(self, "http://localhost%s" % path, transport=PipeTransport(input, output), allow_none=True)

class Server(SimpleXMLRPCDispatcher):
    transport = None
    handler = None
    dispatchers = None
    def __init__(self, input=sys.stdin, output=sys.stdout, dispatchers=None):
        SimpleXMLRPCDispatcher.__init__(self, allow_none=True, encoding=None)
        if not dispatchers:
            dispatchers = {
                '/RPC2' : self
            }
        self.transport = PipeTransport(input, output)
        self.transport.tagname = "Server"
        self.transport.timeout = None
        self.dispatchers = dispatchers
        
    def serve_forever(self):
        try:
            while True:
                try:
                    self.process_one()
                except IOError:
                    if sys.exc_info()[1].errno == 32: # Broken pipe
                        break
                    else:
                        raise
        finally:
            self.transport.close()
                    
    def process_one(self):
        try:
            path, data = self.transport.read_item()
            response = self.do_dispatch(data, path)
            self.transport.write_item(path, response)
        except Exception: # Internal error
            self.transport.close()
            raise
    
    def do_dispatch(self, data, path):
        try:
            dispatcher = self.dispatchers.get(path)
            if not dispatcher:
                raise xmlrpclib.ResponseError("No dispatcher for path '%s'" % path)
            kw = dict()
            if path and path != "/RPC2":
                kw["path"] = path
            response = dispatcher._marshaled_dispatch(data, **kw)
        except:
            # report low level exception back to server
            # (each dispatcher should have handled their own
            # exceptions)
            exc_type, exc_value = sys.exc_info()[:2]
            response = xmlrpclib.dumps(
                xmlrpclib.Fault(1, "%s:%s" % (exc_type, exc_value)),
                allow_none=True)
        return response

