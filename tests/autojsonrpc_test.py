import xmlrpc_test
import streamrpc

class XmlAutoDetectTests(xmlrpc_test.XmlTests):
    def _servertype(self):
        return "streamrpc.Server"