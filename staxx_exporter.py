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

# Consts
REQUEST_TIMEOUT = 10

def test_script():
    """
    Test function (for pytest)
    """
    # TODO
    # dxl_config = None
    # dxl_config = DxlClientConfig.create_dxl_config_from_file('conf/dxl/sample_dxlclient.config')
    # if not dxl_config:
	#    exit(1)
    exit(0)

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
    parser.add_argument("-c", "--configfile", help="Configuration file.", default="/etc/opendxl-anomali-staxx/client.conf")
    parser.add_argument("-d", "--dryrun", help="Export observables from STAXX without generating DXL messages.", action='store_true', default=False)
    parser.add_argument("-l", "--loglevel", help="Logging level (DEBUG, INFO or ERROR).", default="INFO")
    parser.add_argument("-p", "--pprint", help="Pretty print exported observables to STDOUT.", action='store_true', default=False)
    parser.add_argument("-s", "--singleshot", help="Single shot mode (will not keep polling STAXX server).", action='store_true', default=False)
    parser.add_argument("-t", "--time", help="Polling time (in seconds).", default=60)    

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
        response = requests.post(url, content, headers=headers, verify=False, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        logger.error("Error connecting to STAXX server ({0})!".format(e.message))
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
        A tuple (error, json), where 'error' equals True on failure, and 'json' contains the JSON response (None on failure).
    """

    # build the request 
    headers = {'Content-Type': 'application/json'}
    url = "https://{}:{}/api/v1/intelligence".format(address,port)
    content = json.dumps({"token": token, "query": query, "type": "json"}).encode("utf-8")
    try:
        logger.info("Connecting to STAXX server (observables exporting)...")
        response = requests.post(url, content, headers=headers, verify=False, timeout=REQUEST_TIMEOUT)
    except:
        logger.error("Error connecting to STAXX server...")
        return True, None

    if response.status_code != 200:
        logger.error("Could not export STAXX observables. Reason: {0}".format(response.reason))
        return True, None
    else:
        #get the data from the response
        logger.debug("Response code is 200. Retrieving data...")
        json_obj = response.json()
        if len(json_obj) < 1:
            logger.debug("JSON response is empty!")
            return False, None
        logger.debug("JSON response ok!")
        return False, json_obj

def is_observable_type_listed(values, searchFor):
    """
    TODO

    Returns:
        TODO
    """
    for k in values:
        for v in values[k]:
            if searchFor in v:
                return k
    return None

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
        config = ConfigObj(args.configfile, raise_errors=True, file_error=True)
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
        # build the topics
        #
        obs_types = config['Observable Types']
        logger.debug("Observable types: %s", obs_types)
        obs_topics = config['Observable Topics']
    #
    # timed loop (synchronous "obs export / msg publish")
    #
    while True:
        #
        # export observables into JSON object
        # 
        req_error, json_obs = get_staxx_observables(config['STAXX']['Address'],config['STAXX']['Port'],
                                                    token, args.filter_query)
        if req_error:
            logger.error("Failure exporting observables.")
            if not args.singleshot:
                logger.info("Sleeping until next polling cycle...\n")
                time.sleep(args.time)
                logger.info("New polling cycle.")
                continue
        if json_obs:
            logger.info("{0} observable(s) exported from Anomali STAXX.".format(len(json_obs)))
            if args.pprint: 
                logger.info("Printing observables to STDOUT...")
                print json.dumps(json_obs, indent=2,sort_keys=False)
            if not args.dryrun:
                #
                # Connect to DXL and publish the observables as events
                #
                try:
                    with DxlClient(dxl_config) as dxl_client:
                        # Connect to DXL Broker
                        logger.info("Connecting to DXL broker...")
                        dxl_client.connect()
                        # TODO - handle possible connection errors
                        logger.info("Filtering observables and publishing events...")
                        count = 0
                        for ob in json_obs:
                            key = is_observable_type_listed(obs_types, ob['itype'])
                            if key:
                                count += 1
                                logger.debug("Publishing message for observable (itype: %s, topic: %s).", ob['itype'], obs_topics[key])
                                dxl_event = Event(obs_topics[key])
                                payload_str = json.dumps(ob)
                                logger.debug("Msg payload: %s", payload_str)
                                dxl_event.payload = str(payload_str).encode()
                                dxl_client.send_event(dxl_event)
                            else:
                                logger.info("Observable not published (itype: %s not listed).", ob['itype'])
                        logger.info("%s event(s) published to DXL fabric.", count)
                except Exception as e:
                    logger.error("Could not initialize OpenDXL client ({0}).".format(e.message))
                    exit(1)
        else:
            logger.info("No observable exported from Anomali STAXX.")    
        
        # wait for next cycle (if not single shot mode)
        if args.singleshot:
            logger.info("Exiting (single shot mode).")
            exit(0)
        else:
            logger.info("Sleeping until next polling cycle...\n")
            time.sleep(args.time)
            logger.info("New polling cycle.")

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        # TODO - gracefully exit
        logger.info("Caught keyboard interrupt signal. Exiting...")
        exit(0)
