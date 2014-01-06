from __future__ import print_function
import unittest
import sys, os
import subprocess
import piperpclib

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
    raise piperpclib.Fault(42, "A Fault")

class BasicTests(unittest.TestCase):

    def test_unsupported_method(self):
        rpc = _server()
        try:
            rpc.unsupported_method()
        except piperpclib.Fault, f:
            assert "is not supported" in f.faultString

    def test_parameterless(self):
        rpc = _server()
        value = rpc.test_parameterless()
        assert value == "Value"

    def test_parameters(self):
        rpc = _server()
        value = rpc.test_parameters("Hello", True)
        assert value == "Value: Hello, True"

    def test_None(self):
        rpc = _server()
        value = rpc.test_passthrough(None)
        assert value is None

    def test_list(self):
        rpc = _server()
        input = [1,2,3,4,5]
        value = rpc.test_passthrough(input)
        assert value == input

    def test_tuple(self):
        rpc = _server()
        input = (1,2,3,4,5)
        value = rpc.test_passthrough(input)
        assert value == list(input)

    def test_boolean(self):
        rpc = _server()
        value = rpc.test_passthrough(False)
        assert value == False

    def test_large_structure(self):
        rpc = _server()
        input = list(range(100000))
        value = rpc.test_passthrough(input)
        assert value == input

    def test_exception(self):
        rpc = _server()
        try:
            value = rpc.test_exception()
        except piperpclib.Fault, f:
            assert f.faultCode == 1
            assert f.faultString == "<type 'exceptions.Exception'>:A regular Python exception"

    def test_fault(self):
        rpc = _server()
        try:
            value = rpc.test_fault()
        except piperpclib.Fault, f:
            assert f.faultCode == 42
            assert f.faultString == "A Fault"

def _server(path="/RPC2"):
    proc = subprocess.Popen(["python", __file__, "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    rpc = piperpclib.ServerProxy(process=proc, path=path)
    return rpc

if __name__ == '__main__':    
    # simple self test
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        #print("Server is %d" % os.getpid(), file=sys.stderr)
        rpc = piperpclib.Server()
        rpc.register_function(test_parameterless)
        rpc.register_function(test_parameters)
        rpc.register_function(test_passthrough)
        rpc.register_function(test_exception)
        rpc.register_function(test_fault)
        rpc.serve_forever()
    elif len(sys.argv) > 1 and sys.argv[1] == "multiserve":
        #print("Server is %d" % os.getpid(), file=sys.stderr)
        d1 = piperpclib.SimpleXMLRPCDispatcher(allow_none=True)
        d1.register_function(test_parameterless)
        d2 = piperpclib.SimpleXMLRPCDispatcher(allow_none=True)
        d2.register_function(test_parameterless_alt, "test_parameterless")
        rpc = piperpclib.Server(dispatchers={"/A" : d1, "/B" : d2})
        rpc.serve_forever()
    else:
        unittest.main(verbosity=2)
        