#!/usr/bin/env python
# -*- coding: utf-8 -*
import os
from setuptools import setup

ROOT_DIR = os.path.dirname(__file__)
SOURCE_DIR = os.path.join(ROOT_DIR)

test_requirements = []
requirements = ['splitstream>=1.2.0','json-rpc>=1.9.2']

setup(
    name="streamrpc",
    url="https://github.com/evolvIQ/streamrpc",
    author="Rickard Lyrenius",
    author_email="rickard@evolviq.com",
    version='1.0.0',
    description="XML-RPC / JSON-RPC over pipe pair.",
    py_modules=['streamrpc'],
    install_requires=requirements + test_requirements,
    zip_safe=True,
    classifiers=["License :: OSI Approved :: Apache Software License", "Topic :: Software Development :: Libraries :: Python Modules"],
    test_suite='tests'
)
