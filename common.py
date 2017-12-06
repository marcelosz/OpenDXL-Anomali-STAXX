#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""common.py - 
  Common definitions and functions for the DXL client.
"""
import logging

# DXL message root topic
DXL_MSG_ROOT_TOPIC = "/staxx/observable"

# Enable logging, this will also direct built-in DXL log messages.
# See - https://docs.python.org/2/howto/logging-cookbook.html
log_formatter = logging.Formatter('%(asctime)s staxx-exporter (%(name)s) %(levelname)s: %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logger = logging.getLogger()
logger.addHandler(console_handler)

def setLevel(lg, level):
    """
    Set the level of verbosity of a logger instance.
    """
    # Configure logging level
    if level == 'DEBUG':
        lg.setLevel(logging.DEBUG)
    elif level == 'INFO':
        lg.setLevel(logging.INFO)
    elif level == 'WARNING':
        lg.setLevel(logging.WARNING)   
    else:
        lg.setLevel(logging.ERROR)