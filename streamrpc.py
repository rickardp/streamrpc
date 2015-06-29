# -*- coding: utf-8 -*
#
#   piperpc.py
#   piperpc - XML-RPC/JSON-RPC over raw streams (pipes, SSH tunnels, 
#             raw TCP sockets, etc)
#
#   Copyright © 2015 Rickard Lyrenius
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

"""XML-RPC/JSON-RPC over file handles (pipes, SSH tunnels, TCP sockets, etc)

Example (client):
-----------------

    proc = subprocess.Popen(["ssh","myserver","python", "server.py"], 
       stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    
    rpc = piperpclib.XmlClient(process=proc, path=path)
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
import sys, os, io
import traceback
import splitstream
import json
try:
    import xmlrpclib
    __OLDSTYLE_XMLRPC_PACKAGES = True
except ImportError:
    __OLDSTYLE_XMLRPC_PACKAGES = False
    
if __OLDSTYLE_XMLRPC_PACKAGES:
    from xmlrpclib import Fault
    from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
    BUF = lambda _:_
else:
    from xmlrpc.client import Fault
    import xmlrpc.client as xmlrpclib
    from xmlrpc.server import SimpleXMLRPCDispatcher
    BUF = lambda s:bytes(s,'UTF-8')

__ALL__ = ["Server", "XmlClient", "XmlServer", "JsonClient", "JsonServer"]
        
def _ios(input, output, process, socket):
    if process:
        if input or output or socket:
            raise ValueError("Parameters input, output, socket are mutually exclusive with process")
        return (_wrapinput(process.stdout), process.stdin)
    elif socket:
        if input or output:
            raise ValueError("Parameters input, output are mutually exclusive with socket")
        class SocketReader:
            def read(n):
                return socket.recv(n)
        class SocketWriter:
            def write(n):
                socket.send(n)
            close = socket.close
        return (SocketReader(), SocketWriter())
    else:
        return (_wrapinput(input), output)
        
def _wrapinput(f):
    fd = -1
    try:
        fd = int(f.fileno())
    except:
        return f
    
    try:
        # Set file descriptor to nonblocking. Does not work on Windows
        import fcntl, select, stat
        fmode = os.fstat(fd).st_mode
        if stat.S_ISFIFO(fmode) or stat.S_ISCHR(fmode) or stat.S_ISSOCK(fmode):
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            rd = f.read
            def my_read(n):
                while True:
                    try:
                        d = rd(n)
                    except IOError,e:
                        if e.errno == 35:
                            select.select([fd], [], [], 1)
                            continue
                        raise
                    break
                return d
            
            class InputWrapper(object):
                def __init__(self, read_func):
                    self.read = read_func
            f = InputWrapper(my_read)
    except ImportError:
        pass
            
        
    return f
    
        
class Method(object):
    def __init__(self, request, name):
        self.__request = request
        self.__name = name
    def __getattr__(self, name):
        return Method(self.__request, "%s.%s" % (self.__name, name))
    def __call__(self, *args, **kw):
        return self.__request(self.__name, args, kw)
        
class XmlClient(object):
    def __init__(self, input=None, output=None, process=None, socket=None, allow_none=True, encoding=None):
        self.__input, self.__output = _ios(input, output, process, socket)
        self.__encoding = encoding
        self.__allow_none = allow_none
        self.__split = splitstream.splitfile(self.__input, format="xml")
        
    def _request(self, name, args, kwargs):
        if kwargs: raise NotImplemented("Keyword arguments not supported in XML-RPC mode")
        req = xmlrpclib.dumps(args, name, encoding=self.__encoding, allow_none=self.__allow_none)
        self.__output.write(req)
        self.__output.flush()
        for xml in self.__split:
            return xmlrpclib.loads(xml, self.use_datetime)[0][0]

    def __getattr__(self, name):
        return Method(self._request, name)
        
class JsonClient(object):
    def __init__(self, input=None, output=None, process=None, socket=None, version=2):
        self.__input, self.__output = _ios(input, output, process, socket)
        self.__split = splitstream.splitfile(self.__input, format="json")
        if version not in (1,2):
            raise ValueError("version should be 1 or 2")
        self.__version = version
        self.__id = 1 # Not really used in synchronous mode
        
    def _request(self, name, args, kwargs):
        if self.__version == 1:
            if kwargs:
                raise NotImplemented("Keyword arguments not supported in JSON-RPC 1.0 mode")
            req = json.dumps({ "method" : name, "params" : list(args), "id" : self.__id })
        else:
            if kwargs:
                if args:
                    raise NotImplemented("Keyword arguments cannot be combined with positional arguments in JSON-RPC mode")
                req = json.dumps({ "jsonrpc" : "2.0", "method" : name, "params" : kwargs, "id" : self.__id })
            else:
                req = json.dumps({ "jsonrpc" : "2.0", "method" : name, "params" : list(args), "id" : self.__id })
        self.__id += 1
        self.__output.write(req)
        self.__output.flush()
        for s in self.__split:
            retobj = json.loads(s)
            if "error" in retobj:
                e = retobj["error"]
                ec = e.get("code", -32000)
                #if ec > -32100:
                raise Fault(ec, e.get("message", "#%s" % ec))
                #else:
                #    raise jsonrpc.exceptions.JSONRPCServerError(
            else:
                return retobj["result"]

    def __getattr__(self, name):
        return Method(self._request, name)
        
class Server(object):
    """Server that can respond to both JSON-RPC and XML-RPC requests and will respond
    with the protocol of the request."""
    def __init__(self, input=sys.stdin, output=sys.stdout, process=None, socket=None, close=True):
        self.input, self.output = _ios(input, output, process, socket)
        if not self.input:
            raise ValueError("Input was not set")
        if not self.output:
            raise ValueError("Output was not set")
        self.inner = None
        self.regs = []
        self.__close = close
        
    def serve_forever(self):
        try:
            while True:
                try:
                    self.process_one()
                except EOFError:
                    break
                except IOError:
                    if sys.exc_info()[1].errno == 32: # Broken pipe
                        break
                    else:
                        raise
        finally:
            sys.stderr.flush()
            self.close()
            
    def _close_file(self, f):
        # Never close stdin or stderr, but close stdout to signify EOF if necessary
        if self.__close and f and (sys is None or not f in (sys.stdin, sys.stderr)) and hasattr(f, 'close'):
            f.close()
    
    def close(self):
        self._close_file(self.input)
        self._close_file(self.output)
                    
    def process_one(self):
        n = False
                
        while not self.inner:
            n = True
            s = self.input.read(1)
            if s == '<':
                self.inner = XmlServer(self.input, self.output, preamble=s)
            elif s in '{[':
                self.inner = JsonServer(self.input, self.output, preamble=s)
        if n:
            for a,kw in self.regs:
                self.inner.register_function(*a, **kw)
            self.regs = []
        self.inner.process_one()
        
    def register_function(self, *a, **kw):
        if self.inner:
            self.inner.register_function(*a, **kw)
        else:
            self.regs.append((a, kw))

class XmlServer(Server):
    """XML-RPC server"""
    def __init__(self, input=sys.stdin, output=sys.stdout, process=None, socket=None, close=True, allow_none=True, encoding=None, use_datetime=0, preamble=""):
        Server.__init__(self, input, output, process, socket, close)
        self.dispatcher = SimpleXMLRPCDispatcher(allow_none=allow_none, encoding=encoding)
        self.allow_none = allow_none
        self.encoding = encoding
        self.chunks = splitstream.splitfile(self.input, format="xml", maxdocsize=1024*1024*120, preamble=preamble)
        self.use_datetime = use_datetime
        self.register_function = self.dispatcher.register_function
                    
    def process_one(self):
        try:
            for xml in self.chunks:
                p,m = xmlrpclib.loads(xml, self.use_datetime)
                response = self.do_dispatch(p,m)
                self.output.write(response)
                self.output.flush()
                return
            raise EOFError()
        except Exception: # Internal error
            self.close()
            raise
    
    def do_dispatch(self, params, method):
        try:
            rsp = self.dispatcher._dispatch(method, params)
            response = xmlrpclib.dumps((rsp,), allow_none=self.allow_none, encoding=self.encoding)
        except Fault, fault:
            response = xmlrpclib.dumps(fault, allow_none=self.allow_none, encoding=self.encoding)
        except:
            exc_type, exc_value, exc_tb = sys.exc_info()
            response = xmlrpclib.dumps(
                xmlrpclib.Fault(1, "%s:%s" % (exc_type, exc_value)),
                encoding=self.encoding, allow_none=self.allow_none)
        return response

class JsonServer(Server):
    """JSON-RPC server"""
    def __init__(self, input=sys.stdin, output=sys.stdout, process=None, socket=None, close=True, preamble=""):
        Server.__init__(self, input, output, process, socket, close)
        self.dispatcher = {}
        self.chunks = splitstream.splitfile(self.input, format="json", maxdocsize=1024*1024*120, preamble=preamble)
        
    def register_function(self, func, name=None):
        self.dispatcher[name or func.__name__] = func
                    
    def process_one(self):
        try:
            for s in self.chunks:
                ret = self.do_dispatch(s)
                response = json.dumps(ret)
                self.output.write(response)
                self.output.flush()
                return
            raise EOFError()
        except Exception: # Internal error
            self.close()
            raise
            
    def do_dispatch(self, s):
        try:
            obj = json.loads(s)
        except (TypeError, ValueError):
            return {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}
        v = None
        if "jsonrpc" in obj:
            if obj["jsonrpc"] == "2.0":
                v = 2
        else:
            v = 1
        method = obj.get("method")
        reqid = obj.get("id")
        notify = not "id" in obj
        if v is None or method is None:
            if v == 1:
                return {"error": {"code": -32600, "message": "Invalid Request"}, "id": reqid}
            else:
                return {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": reqid}
        prm = obj.get("params")
        aprm = ()
        kwprm = {}
        if isinstance(prm, list):
            aprm = prm
        elif isinstance(prm, dict) and v == 2:
            kwprm = prm
        else:
            if v == 1:
                return {"error": {"code": -32602, "message": "Invalid params"}, "id": reqid}
            else:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params"}, "id": reqid}
        mi = self.dispatcher.get(method)
        if not mi:
            if v == 1:
                return {"error": {"code": -32601, "message": "Method not found"}, "id": reqid}
            else:
                return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": reqid}
        try:
            ret = mi(*aprm, **kwprm)
        except Fault,f:
            return {"jsonrpc": "2.0", "error": {"code": f.faultCode, "message": f.faultString or ("#%s" % f.faultCode)}, "id": reqid}
        except:
            return {"jsonrpc": "2.0", "error": {"code": -32000, "message": str(sys.exc_info()[1])}, "id": reqid}
        
        if v == 1:
            return {"result":ret, "id": reqid}
        else:
            return {"jsonrpc": "2.0", "result":ret, "id": reqid}
        
    