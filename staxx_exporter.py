#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""staxx_exporter.py - 
  Main OpenDXL-Anomali-STAXX client script. 
  Connects to Anomali STAXX and McAFee DXL messaging bus, exporting observables 
  from one into the other as messages. """

__author__ = "Marcelo Souza"
__license__ = "GPL"

import sys, logging, argparse, textwrap
import requests, json, re, urllib3, time

# Enable logging, this will also direct built-in DXL log messages.
# See - https://docs.python.org/2/howto/logging-cookbook.html
log_formatter = logging.Formatter('%(asctime)s staxx-exporter (%(name)s) %(levelname)s: %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.addHandler(console_handler)

# Config
from configobj import ConfigObj, ConfigObjError
config = None

# DXL imports
from dxlclient.client import DxlClient
from dxlclient.client_config import DxlClientConfig
from dxlclient.message import Event

# DXL message root topic
DXL_MSG_ROOT_TOPIC = "/staxx/observable"

def create_arg_parser():
    """
    Parses command line arguments.
    
    Returns:
        An ArgumentParser object.
    """

    epilog = """\
       This script works as an OpenDXL client for Anomali STAXX, exporting observables
       (IOCs) from it and publishing messages (events) into the DXL bus.
       """
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=textwrap.dedent(epilog))
    parser.add_argument("filter_query", help="Query used to filter desired observables (confidence, type, time window, ...).", metavar="FILTER_QUERY")
    parser.add_argument("-c", "--config_file", help="Configuration file.", default="/etc/opendxl-anomali-staxx/client.conf")
    parser.add_argument("-d", "--dryrun", help="Export observables from STAXX without generating DXL messages.", action='store_true', default=False)
    parser.add_argument("-l", "--loglevel", help="Logging level (DEBUG, INFO or ERROR). If not set, defaults to ERROR.", default="INFO")
    parser.add_argument("-p", "--pprint", help="Pretty print exported observables to STDOUT. Defaults to false.", action='store_true', default=False)
    parser.add_argument("-t", "--time", help="Polling time (in seconds). Defaults to 60.", default=60)    

    return parser

def set_logging_level(lg, level):
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

def get_staxx_token(address,port, user, pwd):
    """
    Get API token from Anomali STAXX server.

    Returns:
        A string representing the token.
    """

    headers = {'Content-Type': 'application/json'}
    url = "https://{}:{}/api/v1/login".format(address,port)
    content = json.dumps({"username": user, "password": pwd}).encode("utf-8")

    try:
        logger.info("Connecting to STAXX server (token retrieval)...")
        response = requests.post(url, content, headers=headers, verify=False)
    except:
        logger.error("Error connecting to STAXX server!")
        return None

    if response.status_code != 200:
        logger.error("Could not retrieve STAXX login token. Please check your credentials.")
        return None
    else:
        token_id = response.json()["token_id"]
        return token_id

def get_staxx_observables(address, port, token, query):
    """
    Get observables.

    Returns:
        A JSON object representing the observables.
    """

    # build the request 
    headers = {'Content-Type': 'application/json'}
    url = "https://{}:{}/api/v1/intelligence".format(address,port)
    content = json.dumps({"token": token, "query": query, "type": "json"}).encode("utf-8")
    try:
        logger.info("Connecting to STAXX server (observables exporting)...")
        response = requests.post(url, content, headers=headers, verify=False)
    except:
        logger.error("Error connecting to STAXX server...")
        return None

    if response.status_code != 200:
        logger.error("Could not export STAXX observables. Reason: {0}".format(response.reason))
        return None
    else:
        #get the data from the response
        return response.json()

def publish_dxl_message(payload):
    """
    Publish a message to the DXL fabric.

    Returns:
        TODO
    """
    return payload

###############################################################################

def main(argv):
    # parse the args
    arg_parser = create_arg_parser()
    args = arg_parser.parse_args()

    # set logging level
    set_logging_level(logger, args.loglevel)
    # configure local logger for requests (Urllib3) and set its level
    set_logging_level(logging.getLogger("urllib3"), args.loglevel)
    # read cfg file
    try:
        config = ConfigObj(args.config_file, raise_errors=True, file_error=True)
    except:
        # TODO - enhance error handling here 
        logger.error("Could not parse config file!")
        exit(1)

    #
    # get token
    #
    # TODO - handle HTTPS nicely 
    urllib3.disable_warnings()
    token = get_staxx_token(config['STAXX']['Address'],config['STAXX']['Port'],
                            config['STAXX']['User'],config['STAXX']['Password'])
    if not token:
        logger.error("Exiting...")
        exit(1)

    #
    # DXL initialization
    #
    # TODO - enhance error handling here 
    if not args.dryrun:
        # DxlClientConfig from DXL configuration file
        logger.info("Loading DXL config from: %s", config['DXL']['Config'])
        dxl_config = DxlClientConfig.create_dxl_config_from_file(config['DXL']['Config'])

    #
    # timed loop (synchronous "obs export / msg publish")
    #
    while True:
        #
        # export observables into JSON object
        # 
        json_observables = get_staxx_observables(config['STAXX']['Address'],config['STAXX']['Port'],
                                                 token, args.filter_query)
        if not json_observables:
            logger.error("No observables exported due to error. Sleeping until next cycle.")
            time.sleep(args.time)
            break
        logger.info("{0} observable(s) exported from Anomali STAXX.".format(len(json_observables)))
        if args.pprint: 
            logger.info("Printing observables to STDOUT...")
            print json.dumps(json_observables, indent=2,sort_keys=False)
        if not args.dryrun:
            #
            # Publish the observables as events
            #
            try:
                with DxlClient(dxl_config) as dxl_client:
                    # Connect to DXL Broker
                    logger.info("Connecting to DXL broker...")
                    dxl_client.connect()
                    logger.info("Publishing events...")
                    dxl_event = Event(DXL_MSG_ROOT_TOPIC)
                    dxl_event.payload = str("Whatever").encode()
                    dxl_client.send_event(dxl_event)
            except Exception as e:
                logger.error("Could not initialize OpenDXL client ({0}).".format(e.message))
                exit(1)
        else:
            # Do nothing...
            logger.info("Done! (Dry run mode)")

        # wait for next cycle
        time.sleep(args.time)
        logger.info("New polling cycle...")

if __name__ == "__main__":
    main(sys.argv[1:])
