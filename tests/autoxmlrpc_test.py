import jsonrpc_test
import streamrpc

class JsonAutoDetectTests(jsonrpc_test.JsonTests):
    def _servertype(self):
        return "streamrpc.Server"