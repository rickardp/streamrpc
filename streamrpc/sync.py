# -*- coding: utf-8 -*
#
#   sync.py - Synchronous clients and servers
#   streamrpc - XML-RPC/JSON-RPC over raw streams (pipes, SSH tunnels, 
#               raw TCP sockets, etc)
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

import sys, os, io
import traceback
import splitstream
from . import protocol

EAGAIN = 35
EPIPE = 32
try:
    import errno
    EAGAIN = errno.EAGAIN
    EPIPE = errno.EPIPE
except (ImportError, AttributeError): # Platform does not define error code?
    pass

__ALL__ = ["Server", "XmlClient", "XmlServer", "JsonClient", "JsonServer"]
        
def _ios(input, output, process, socket):
    if process:
        if input or output or socket:
            raise ValueError("Parameters input, output, socket are mutually exclusive with process")
        return (_wrapinput(process.stdout), _wrapoutput(process.stdin))
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
        return (_wrapinput(input), _wrapoutput(output))
        
def _wrapoutput(f):
    if isinstance(f, io.TextIOWrapper):
        f = f.buffer.raw
    return f
    
        
def _wrapinput(f):
    fd = -1
    if isinstance(f, io.TextIOWrapper):
        f = f.buffer
    
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
                        if d is None:
                            select.select([fd], [], [], 1)
                            continue
                    except IOError as e:
                        if e.errno == EAGAIN:
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
        
class Client(object):
    def __init__(self, protocol, input=None, output=None, process=None, socket=None):
        self.__input, self.__output = _ios(input, output, process, socket)
        self.__protocol = protocol
        self.__split = splitstream.splitfile(self.__input, format=protocol.splitfmt())
        
    def __request(self, method, args, kwargs):
        
        r = []
        
        def on_response(response, err):
            if err: raise err
            r.append(response)
            
        req = self.__protocol.initiate_request(method, args, kwargs, on_response)
        self.__output.write(req)
        self.__output.flush()
            
        for s in self.__split:
            self.__protocol.handle_response(s)
            break
            
        if not r:
            raise ValueError("Did not receive a response")
        
        return r[0]

    def __getattr__(self, name):
        return Method(self.__request, name)
        
class XmlClient(Client):
    def __init__(self, input=None, output=None, process=None, socket=None, encoding=None, allow_none=True, use_datetime=0):
        Client.__init__(self, protocol.XmlRpc(encoding, allow_none, use_datetime), input, output, process, socket)
        
class JsonClient(Client):
    def __init__(self, input=None, output=None, process=None, socket=None, version=2):
        Client.__init__(self, protocol.JsonRpc(version), input, output, process, socket)
        
class Server(object):
    """Server that can respond to both JSON-RPC and XML-RPC requests and will respond
    with the protocol of the request."""
    def __init__(self, input=sys.stdin, output=sys.stdout, process=None, socket=None, close=True, protocol=None):
        self.input, self.output = _ios(input, output, process, socket)
        if not self.input:
            raise ValueError("Input was not set")
        if not self.output:
            raise ValueError("Output was not set")
        self.__regs = []
        self.__shouldclose = close
        self.__protocol = protocol
        self.__split = None
        
    def serve_forever(self):
        try:
            while True:
                try:
                    self.process_one()
                except EOFError:
                    break
                except IOError as e:
                    if e.errno == EPIPE: # Broken pipe
                        break
                    else:
                        raise
        finally:
            sys.stderr.flush()
            self.close()
            
    def __close_file(self, f):
        # Never close stdin or stderr, but close stdout to signify EOF if necessary
        if self.__shouldclose and f and (sys is None or not f in (sys.stdin, sys.stderr)) and hasattr(f, 'close'):
            f.close()
    
    def close(self):
        self.__close_file(self.input)
        self.__close_file(self.output)
                    
    def process_one(self):
        got_protocol = False
        
        s = b""
        while not self.__protocol:
            got_protocol = True
            s = self.input.read(1)
            if s == b'<':
                self.__protocol = protocol.XmlRpc()
            elif s in b'{[':
                self.__protocol = protocol.JsonRpc()
        
        if not self.__split:
            self.__split = splitstream.splitfile(self.input, format=self.__protocol.splitfmt(), maxdocsize=1024*1024*120, preamble=s)
        
        if got_protocol:
            for a,kw in self.__regs:
                self.__protocol.register_function(*a, **kw)
            self.__regs = []
        
        try:
            for rsps in self.__split:
                response = self.__protocol.dispatch_request(rsps)
                self.output.write(response)
                self.output.flush()
                return
            raise EOFError()
        except Exception: # Internal error
            self.close()
            raise
        
    def register_function(self, *a, **kw):
        if self.__protocol:
            self.__protocol.register_function(*a, **kw)
        else:
            self.__regs.append((a, kw))

class XmlServer(Server):
    """XML-RPC server"""
    def __init__(self, input=sys.stdin, output=sys.stdout, process=None, socket=None, close=True, encoding=None, allow_none=True, use_datetime=0):
        Server.__init__(self, input, output, process, socket, close, 
            protocol=protocol.XmlRpc(encoding, allow_none, use_datetime))

class JsonServer(Server):
    """JSON-RPC server"""
    def __init__(self, input=sys.stdin, output=sys.stdout, process=None, socket=None, close=True, version=2):
        Server.__init__(self, input, output, process, socket, close, 
            protocol=protocol.JsonRpc(version))
