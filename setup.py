#!/usr/bin/env python
# -*- coding: utf-8 -*
import os
from setuptools import setup

ROOT_DIR = os.path.dirname(__file__)
SOURCE_DIR = os.path.join(ROOT_DIR)

test_requirements = []
requirements = ['splitstream>=1.2.0']

setup(
    name="streamrpc",
    url="https://github.com/evolvIQ/streamrpc",
    author="Rickard Lyrenius",
    author_email="rickard@evolviq.com",
    version='1.0.1',
    description="XML-RPC / JSON-RPC over pipe pair.",
    py_modules=['streamrpc'],
    install_requires=requirements + test_requirements,
    zip_safe=True,
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy"],
    test_suite='tests'
)
