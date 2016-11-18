#!/usr/bin/env python
#coding: utf-8

from setuptools import setup, find_packages
from os import path

setup(
	name = "nosql",
	author = "chongchong wang",
	author_email = "chongchong1110@gmail.com",
	version = "0.1",
	license = "MIT",
	url = "https://github.com/CcWang/nosql",
	download_url = "",
	description = "NoSQL ORM for relational db backed by SQLAlchemy",
    long_description = open(
        path.join(
            path.dirname(__file__),
            'README.md'
        )
    ).read(),
	packages = find_packages(exclude="test"),
	install_requires = ["SQLAlchemy>=0.8.2"],
	scripts = "",
    test_suite = "test"
)
