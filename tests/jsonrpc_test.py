import sys
from . import xmlrpc_test
import streamrpc

class JsonTests(xmlrpc_test.XmlTests):
    def _servertype(self):
        return "streamrpc.JsonServer"
        
    def _clienttype(self, process):
        return streamrpc.JsonClient(process=process)
        
    def test_unsupported_method(self):
        rpc = self._server()
        try:
            rpc.unsupported_method()
        except streamrpc.Fault:
            f = sys.exc_info()[1]
            assert f.faultCode == -32601

    def test_exception(self):
        rpc = self._server()
        try:
            value = rpc.test_exception()
        except streamrpc.Fault:
            f = sys.exc_info()[1]
            assert f.faultCode == -32000
            assert f.faultString == "A regular Python exception"

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