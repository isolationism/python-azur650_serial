#!/usr/bin/env python

# Distutils is the default python packager utility.
#from distutils.core import setup

# Setuptools is a slightly nicer distribution utility that can create 'eggs'.
from setuptools import setup, find_packages

setup(name='azur650_serial',
    version='0.0.1',
    description='Serial control interface for Cambridge Audio Azur 650R 7.1 AVR',
    author='Kevin Williams',
    author_email='kevin@weblivion.com',
    url='http://www.weblivion.com/',
    package_dir={'':'src'},
    packages=find_packages('src'),
    include_package_data=True,
    install_requires=['pyserial'],
    zip_safe=False,
)


