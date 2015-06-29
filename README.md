# streamrpc - XML-RPC and JSON-RPC over raw streams

[![Travis CI status](https://travis-ci.org/evolvIQ/streamrpc.svg)](https://travis-ci.org/evolvIQ/streamrpc)
[![License](https://img.shields.io/github/license/evolvIQ/streamrpc.svg)](https://github.com/evolvIQ/streamrpc/blob/master/LICENSE)
[![PyPi version](https://img.shields.io/pypi/v/streamrpc.svg)](https://pypi.python.org/pypi/streamrpc/)
[![PyPi downloads](https://img.shields.io/pypi/dm/streamrpc.svg)](https://pypi.python.org/pypi/streamrpc/)

`streamrpc` is a Python module that allows setting up RPC communication over a pipe or other raw data stream - any object pair that supports a `read` and `write` method respectively.

The main design goals:

* Require as little as possible of the transport implementation (i.e. `read`, `write` and optionally `close` and `flush`).
* Create no "meta-protocol" (such as HTTP for XML-RPC) around it.
* Otherwise follow the XML-RPC and JSON-RPC specifications.

Major use cases:

* Efficient RPC between subprocesses written in different languages on different architectures.
* RPC over SSH.

Currently not supported:

* Full duplex RPC (i.e. both ends of the pipe can initiate requests). This would be interesting and useful but is not currently supported.
* Asynchronous operation. This is not currently supported, but planned.

## Usage

### Use case: Create server and client subprocess

To create a server, create the `Server` object:

```python
import streamrpc
import subprocess

process = subprocess.Popen("ssh xxx python client.py",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE) 
            # Run client, i.e. from SSH

rpc = streamrpc.Server(process=process)

def echo(val):
	print val
	return val
rpc.register_function(echo)	
rpc.process_one()

```

Note that there is no need to specify whether the server is an XML-RPC or JSON-RPC server: it will detect this from the first incoming request. If this is not desired, the `XmlServer` and `JsonServer` classes also exist.

The client would then be implemented as:

```python
import streamrpc

client = streamrpc.JsonClient()
print >>sys.stderr, client.echo("Hello")
```