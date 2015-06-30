# -*- coding: utf-8 -*
#
#   __init__.py
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

"""XML-RPC/JSON-RPC over file handles (pipes, SSH tunnels, TCP sockets, etc)

Example (client):
-----------------

    proc = streamrpc.Popen(["ssh","myserver","python", "server.py"], 
       stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    
    rpc = streamrpc.XmlClient(process=proc, path=path)
    rpc.my_method("Some","Args")

Example (server):
-----------------

    def my_method(arg1, arg2):
       ...
    
    rpc = streamrpc.Server()
    rpc.register_function(my_method)
    rpc.serve_forever()
"""

from .sync import Server, XmlClient, XmlServer, JsonClient, JsonServer
from .protocol import Fault