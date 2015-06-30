from . import jsonrpc_test

class JsonAutoDetectTests(jsonrpc_test.JsonTests):
    def _servertype(self):
        return "streamrpc.Server"