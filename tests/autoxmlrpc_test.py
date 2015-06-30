from . import xmlrpc_test

class XmlAutoDetectTests(xmlrpc_test.XmlTests):
    def _servertype(self):
        return "streamrpc.Server"