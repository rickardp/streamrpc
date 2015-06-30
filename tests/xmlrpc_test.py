import unittest
import sys, os, json
if len(sys.argv) > 2 and sys.argv[1] == "serve":
    sys.path += json.loads(sys.argv[2])
import subprocess
import streamrpc

def test_parameterless():
    return "Value"

def test_parameterless_alt():
    return "Another Value"
    
def test_parameters(a, b):
    return "Value: %s, %s" % (a, b)
    
def test_passthrough(a):
    return a
    
def test_exception():
    raise Exception("A regular Python exception")
    
def test_fault():
    raise streamrpc.Fault(42, "A Fault")

class XmlTests(unittest.TestCase):
    def _servertype(self):
        return "streamrpc.XmlServer"
        
    def _clienttype(self, process):
        return streamrpc.XmlClient(process=process)
        
    def _testmodule(self):
        return "xmlrpc_test"
    
    def _server(self):
        proc = subprocess.Popen([sys.executable, "-mtests." + self._testmodule(), "serve",json.dumps(sys.path),self._servertype()], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        rpc = self._clienttype(proc)
        return rpc
        
    def test_unsupported_method(self):
        rpc = self._server()
        try:
            rpc.unsupported_method()
        except streamrpc.Fault:
            f = sys.exc_info()[1]
            assert "is not supported" in f.faultString

    def test_parameterless(self):
        rpc = self._server()
        value = rpc.test_parameterless()
        assert value == "Value"

    def test_parameters(self):
        rpc = self._server()
        value = rpc.test_parameters("Hello", True)
        assert value == "Value: Hello, True"

    def test_None(self):
        rpc = self._server()
        value = rpc.test_passthrough(None)
        assert value is None

    def test_list(self):
        rpc = self._server()
        input = [1,2,3,4,5]
        value = rpc.test_passthrough(input)
        assert value == input

    def test_tuple(self):
        rpc = self._server()
        input = (1,2,3,4,5)
        value = rpc.test_passthrough(input)
        assert value == list(input)

    def test_boolean(self):
        rpc = self._server()
        value = rpc.test_passthrough(False)
        assert value == False

    def test_large_structure(self):
        rpc = self._server()
        input = list(range(100000))
        value = rpc.test_passthrough(input)
        assert value == input

    def test_exception(self):
        rpc = self._server()
        try:
            value = rpc.test_exception()
        except streamrpc.Fault:
            f = sys.exc_info()[1]
            assert f.faultCode == 1
            assert "A regular Python exception" in f.faultString

    def test_fault(self):
        rpc = self._server()
        try:
            value = rpc.test_fault()
        except streamrpc.Fault:
            f = sys.exc_info()[1]
            assert f.faultCode == 42
            assert f.faultString == "A Fault"

if __name__ == '__main__':
    if len(sys.argv) > 3 and sys.argv[1] == "serve":
        import time,os
        
        rpc = eval(sys.argv[3])()
        rpc.register_function(test_parameterless)
        rpc.register_function(test_parameters)
        rpc.register_function(test_passthrough)
        rpc.register_function(test_exception)
        rpc.register_function(test_fault)
        rpc.serve_forever()
    else:
        unittest.main(verbosity=2)
        
