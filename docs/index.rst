.. OpenDXL-Anomali-STAXX documentation master file, created by
   sphinx-quickstart on Wed Dec  6 10:45:10 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

OpenDXL-Anomali-STAXX Client
============================

OpenDXL-Anomali-STAXX is a Python client that exports observables (IOCs) from Anomali STAXX 
and generates messages with the observables into a McAfee DXL (Data Exchange Layer) messaging 
fabric.

How to use it
-------------
The client may be invoked by running the **staxx_observable_exporter.py** script (usage instructions
below).

.. argparse::
   :filename: ../staxx_observable_exporter.py
   :func: create_arg_parser
   :prog: staxx_observable_exporter
