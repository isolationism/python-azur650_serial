#!/usr/bin/env python

# Distutils is the default python packager utility.
#from distutils.core import setup

# Setuptools is a slightly nicer distribution utility that can create 'eggs'.
from setuptools import setup, find_packages

setup(name='azur650_serial_control',
    version='0.0.1',
    description='Serial Control Protocol for Sony Televisions (and other devices)',
    author='Kevin Williams',
    author_email='kevin@weblivion.com',
    url='http://www.weblivion.com/',
    package_dir={'':'src'},
    packages=find_packages('src'),
    include_package_data=True,
    install_requires=['pyserial'],
    zip_safe=False,
#    entry_points="""
#        [console_scripts]
#        test_connection = tests.test_connection:run_suite
#    """,
)


