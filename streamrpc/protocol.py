# -*- coding: utf-8 -*
#
#   protocol.py - Protocol dispatcher
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

import sys
try:
    import xmlrpclib
    __OLDSTYLE_XMLRPC_PACKAGES = True
except ImportError:
    __OLDSTYLE_XMLRPC_PACKAGES = False
    
if __OLDSTYLE_XMLRPC_PACKAGES:
    from xmlrpclib import Fault
    from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
else:
    from xmlrpc.client import Fault
    import xmlrpc.client as xmlrpclib
    from xmlrpc.server import SimpleXMLRPCDispatcher
import json

json_dumps = json.dumps
json_loads = json.loads
xmlrpc_dumps = xmlrpclib.dumps
xmlrpc_loads = xmlrpclib.loads
if str != bytes:
    json_dumps = lambda x:bytes(json.dumps(x), "utf8")
    json_loads = lambda x:json.loads(str(x, "utf8"))
    xmlrpc_dumps = lambda x,*a,**kw:bytes(xmlrpclib.dumps(x,*a,**kw), "utf8")
    xmlrpc_loads = lambda x,*a,**kw:xmlrpclib.loads(str(x, "utf8"),*a,**kw)
    
__ALL__ = ["JsonRpc", "XmlRpc", "Fault"]

class JsonRpc(object):
    def __init__(self, version=2):
        self.__id = 1
        self.__version = 2
        self.__reqs = {}
        self.__dispatcher = {}
        
    def splitfmt(self):
        return "json"

    def initiate_request(self, method, args, kwargs, completion):
        reqid = self.__id
        self.__id += 1
        if self.__version == 1:
            if kwargs:
                raise NotImplemented("Keyword arguments not supported in JSON-RPC 1.0 mode")
            req = json_dumps({ "method" : method, "params" : list(args), "id" : reqid })
        else:
            if kwargs:
                if args:
                    raise NotImplemented("Keyword arguments cannot be combined with positional arguments in JSON-RPC mode")
                req = json_dumps({ "jsonrpc" : "2.0", "method" : method, "params" : kwargs, "id" : reqid })
            else:
                req = json_dumps({ "jsonrpc" : "2.0", "method" : method, "params" : list(args), "id" : reqid })
        
        self.__reqs[reqid] = completion
        return req
        
    def handle_response(self, rstr):
        response = json_loads(rstr)
        reqid = response.get("id")
        completion = self.__reqs.get(reqid)
        if not completion: return # Invalid ID response
        del self.__reqs[reqid]
        e = response.get("error")
        if e is not None:
            ec = e.get("code", -32000)
            completion(None, Fault(ec, e.get("message", "#%s" % ec)))
        else:
            completion(response["result"], None)
         
    def dispatch_request(self, reqstr):
        return json_dumps(self._dispatch_request(reqstr))
            
    def _dispatch_request(self, reqstr):
        try:
            obj = json_loads(reqstr)
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
        mi = self.__dispatcher.get(method)
        if not mi:
            if v == 1:
                return {"error": {"code": -32601, "message": "Method not found"}, "id": reqid}
            else:
                return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": reqid}
        try:
            ret = mi(*aprm, **kwprm)
        except Fault as f:
            return {"jsonrpc": "2.0", "error": {"code": f.faultCode, "message": f.faultString or ("#%s" % f.faultCode)}, "id": reqid}
        except:
            return {"jsonrpc": "2.0", "error": {"code": -32000, "message": str(sys.exc_info()[1])}, "id": reqid}
        
        if v == 1:
            return {"result":ret, "id": reqid}
        else:
            return {"jsonrpc": "2.0", "result":ret, "id": reqid}
    
    def register_function(self, func, name=None):
        self.__dispatcher[name or func.__name__] = func
            
class XmlRpc(object):
    def __init__(self, encoding=None, allow_none=True, use_datetime=0):
        self.__queue = []
        self.__encoding = encoding
        self.__allow_none = allow_none
        self.__use_datetime = use_datetime
        self.__dispatcher = SimpleXMLRPCDispatcher(allow_none=allow_none, encoding=encoding)
        
    def splitfmt(self):
        return "xml"
        
    def initiate_request(self, method, args, kwargs, completion):
        if kwargs: raise NotImplemented("Keyword arguments not supported in XML-RPC mode")
        self.__queue.append(completion)
        return xmlrpc_dumps(args, method, encoding=self.__encoding, allow_none=self.__allow_none)
        
    def handle_response(self, rstr):
        completion = self.__queue.pop(0)
        try:
            response = xmlrpc_loads(rstr, self.__use_datetime)
            completion(response[0][0], None)
        except Fault as f:
            completion(None, f)
    
    def dispatch_request(self, reqstr):
        p,m = xmlrpc_loads(reqstr, self.__use_datetime)
        try:
            rsp = self.__dispatcher._dispatch(m, p)
            response = xmlrpc_dumps((rsp,), allow_none=self.__allow_none, encoding=self.__encoding)
        except Fault as fault:
            response = xmlrpc_dumps(fault, allow_none=self.__allow_none, encoding=self.__encoding)
        except:
            exc_type, exc_value, exc_tb = sys.exc_info()
            response = xmlrpc_dumps(
                Fault(1, "%s:%s" % (exc_type, exc_value)),
                encoding=self.__encoding, allow_none=self.__allow_none)
        return response
        
    def register_function(self, func, name=None):
        self.__dispatcher.register_function(func, name)
        