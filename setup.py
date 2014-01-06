#!/usr/bin/env python
# -*- coding: utf-8 -*
import os
from setuptools import setup

ROOT_DIR = os.path.dirname(__file__)
SOURCE_DIR = os.path.join(ROOT_DIR)

test_requirements = []
requirements = []

setup(
    name="piperpclib",
    url="https://github.com/evolvIQ/piperpclib",
    author="Rickard Petzäll",
    author_email="rickard@petzall.com",
    version='0.0.1',
    description="XML-RPC over pipe pair.",
    py_modules=['piperpclib'],
    install_requires=requirements + test_requirements,
    zip_safe=True,
    test_suite='tests.test'
)
