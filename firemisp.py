#!/usr/bin/env python


# FireMisp - Python script for pushing FireEye json alerts
# into MISP over http
#
# Alexander Jaeger (deralexxx)
#
# The MIT License (MIT) see https://github.com/deralexxx/FireMISP/blob/master/LICENSE
#
# Based on the idea of:
# Please see: https://github.com/spcampbell/firestic
#

import ConfigParser
import logging
from BaseHTTPServer import BaseHTTPRequestHandler
from BaseHTTPServer import HTTPServer
from SocketServer import ThreadingMixIn
import simplejson as json

try:
    from pymisp import PyMISP
    HAVE_PYMISP = True
except:
    HAVE_PYMISP = False

from pyFireEyeAlert import pyFireEyeAlert

config = ConfigParser.RawConfigParser()
config.read('config.cfg')

# set config values
misp_url = config.get('MISP', 'misp_url')
misp_key = config.get('MISP', 'misp_key')
misp_verifycert = config.getboolean('MISP', 'misp_verifycert')

firemisp_ip = config.get('FireMisp', 'httpServerIP')
firemisp_port = config.getint('FireMisp', 'httpServerPort')
firemisp_logfile = config.get('FireMisp', 'logFile')


#init logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def init_misp(url, key):
    """

    :param url:
    :type url:
    :param key:
    :type key:
    :return:
    :rtype:
    """
    return PyMISP(url, key, misp_verifycert, 'json')


class MyRequestHandler(BaseHTTPRequestHandler):

    logger.debug("my request handler")
    # ---------- GET handler to check if httpserver up ----------
    def do_GET(self):
        logger.debug("someone get")
        pingresponse = {"name": "FireMisp is up"}
        if self.path == "/ping":
            self.send_response(200)
            self.send_header("Content-type:", "text/html")
            self.wfile.write("\n")
            json.dump(pingresponse, self.wfile)
        else:
            self.send_response(200)
            self.send_header("Content-type:", "text/html")
            self.wfile.write("\n")
            json.dump(pingresponse, self.wfile)

    # -------------- POST handler: where the magic happens --------------
    def do_POST(self):
        logger.debug("someone sended a post")
        # get the posted data and remove newlines
        data = self.rfile.read(int(self.headers.getheader('Content-Length')))
        clean = data.replace('\n', '')
        try:
            # Write the data to a file as well for debugging later on
            import datetime
            filename1 = './testing/real/'+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            f = open(filename1, 'w')
            f.write(data)
            f.close

            theJson = json.loads(clean)

            self.send_response(200)
            self.end_headers()
            #processAlert(theJson)
            # deal with multiple alerts embedded as an array
            if isinstance(theJson['alert'], list):
    #            alertJson = theJson
    #            del alertJson['alert']
                for element in theJson['alert']:
                    alertJson = {}  # added for Issue #4
                    alertJson['alert'] = element
                    logger.info("Processing FireEye Alert: " + str(alertJson['alert']['id']))
                    processAlert(alertJson)
            else:
                logger.debug("Processing FireEye Alert: " + str(theJson['alert']['id']))
                processAlert(theJson)

        except ValueError as e:
            logger.error("Value Error2: %s %s",e.message,e.args)
            self.send_response(500)

# ---------------- end class MyRequestHandler ----------------


# ---------------- Class handles requests in a separate thread. ----------------

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
	pass

# ---------------- end class ThreadedHTTPServer ----------------



def processAlert(p_json):

    """
    create pyFireEyeAlert Instance of the json and makes all the mapping

    :param p_json:
    :type p_json:
    """

    logger.debug(p_json)
    fireinstance = pyFireEyeAlert(p_json)

    # This comment will be added to every attribute for reference
    auto_comment = "Auto generated by FireMisp "+ (fireinstance.alert_id)

    # create a MISP event
    logger.debug("alert %s ",fireinstance.alert_id)

    has_previous_event = True

    event = check_for_previous_events(fireinstance)

    map_alert_to_event(auto_comment, event, fireinstance)


def check_for_previous_events(fireeye_alert):

    """
    Default: no previous event detected


    check for:
        alert_id | ['alert']['id']

    :param fireeye_alert:
    :type fireeye_alert:
    :return:
        event id if an event is there
        false if no event is present
    :rtype:
    """
    event = False

    # TODO: de-duplication is still an issue and the following is a bit hacky

    if event == False:
        # Based on alert id
        if fireeye_alert.alert_id:
            result = misp.search_all(fireeye_alert.alert_id)
            logger.debug("searching for %s result: %s", fireeye_alert.alert_id,result)
            event = check_misp_all_result(result)

        from urllib import quote
        # Based on Alert Url

        if fireeye_alert.alert_url and event == False:
            result = misp.search_all(quote(fireeye_alert.alert_url))
            logger.debug("searching for %s result: %s", fireeye_alert.alert_url,result)
            event = check_misp_all_result(result)

        # Based on ma_id
        if fireeye_alert.alert_ma_id and event == False:
            result = misp.search_all(quote(fireeye_alert.alert_ma_id))
            logger.debug("searching for %s result: %s", fireeye_alert.alert_ma_id,result)
            event = check_misp_all_result(result)


        # TODO: complete that
        # combine two criterias e.g. from and to adress
        #if fireeye_alert.attacker_email:
        #    result = misp.search_all(quote(fireeye_alert.attacker_email))

        #   if fireeye_alert.victim_email:
        #        result2 = misp.search_all(quote(fireeye_alert.victim_email))



        # check if source machine and destination are already known
        #TODO improve that!

        source_event_1 = None
        dest_event_2 = None
        event_3 = None

        if fireeye_alert.alert_src_domain and event == False:
            result = misp.search_all(quote(fireeye_alert.alert_src_domain))
            logger.debug("searching for %s result: %s", fireeye_alert.alert_ma_id, result)
            source_event_1 = check_misp_all_result(result)

        if fireeye_alert.dst_ip and event == False:
            result = misp.search_all(quote(fireeye_alert.dst_ip))
            dest_event_2 = check_misp_all_result(result)

        # if not already an source event was found
        if fireeye_alert.alert_src_ip and source_event_1 == None and event == False:
            result = misp.search_all(quote(fireeye_alert.alert_src_ip))
            source_event_1 = check_misp_all_result(result)


        if source_event_1 != None and dest_event_2 != None and source_event_1 == dest_event_2:
            event = dest_event_2

        #check if root infection is the same:
        if fireeye_alert.root_infection:
            result = misp.search_all(quote(fireeye_alert.root_infection))
            event =  check_misp_all_result(result)

    # if one of the above returns a value:
    previous_event = event
    # this looks hacky but it to avoid exceptions if there is no ['message within the result']

    if previous_event != '' and previous_event != False and previous_event != None:
        logger.debug("Will append my data to: %s", previous_event)
        event = misp.get(str(previous_event))  # not get_event!
    else:
        logger.debug("Will create a new event for it")
        # TODO: set occured day
        # misp is expecting: datetime.date.today().isoformat()
        if fireeye_alert.occured:
            logger.debug("Date will be %s", fireeye_alert.occured)
            # event = misp.new_event(0, 2, 0, "Auto generated by FireMisp " + fireinstance.alert_id,str(fireinstance.occured))
            event = misp.new_event(0, 2, 0, "Auto generated by FireMisp " + fireeye_alert.alert_id)

        else:
            event = misp.new_event(0, 2, 0, "Auto generated by FireMisp " + fireeye_alert.alert_id)
    return event


def check_misp_all_result(result):
    logger.debug("Checking %s if it contains previous events",result)
    if 'message' in result:
        if result['message'] == 'No matches.':
            logger.error("No previous event found")
            # has really no event
            return False
    elif 'Event' in result:
        for e in result['response']:
            logger.debug("found a previous event!")
            previous_event = e['Event']['id']
            return previous_event
            break
    else:
        for e in result['response']:
            logger.debug("found a previous event!")
            previous_event = e['Event']['id']
            return previous_event
            break


def map_alert_to_event(auto_comment, event, fireeye_alert):
    """

    START THE MAPPING here
    general info that should be there in every alert
    internal reference the alert ID


    :param auto_comment:
    :type auto_comment:
    :param event:
    :type event:
    :param fireeye_alert:
    :type fireeye_alert:
    """


    misp.add_internal_text(event, fireeye_alert.alert_id, False, auto_comment)
    ### Start Tagging here
    # TLP change it if you want to change default TLP
    misp.add_tag(event, "tlp:amber")
    # General detected by a security system. So reflect in a tag
    misp.add_tag(event, "veris:discovery_method=\"Int - security alarm\"")
    # Severity Tag + Threat level of the Event
    if fireeye_alert.alert_severity:
        if fireeye_alert.alert_severity == 'majr':
            misp.add_tag(event, "csirt_case_classification:criticality-classification=\"1\"")
            # upgrade Threat level if set already
            misp.change_threat_level(event, 1)
        elif fireeye_alert.alert_severity == 'minr':
            misp.add_tag(event, "csirt_case_classification:criticality-classification=\"3\"")
            misp.add_tag(event, "veris:impact:overall_rating = \"Insignificant\"")
            misp.change_threat_level(event, 3)
        else:
            misp.add_tag(event, "csirt_case_classification:criticality-classification=\"3\"")
            misp.add_tag(event, "veris:impact:overall_rating = \"Unknown\"")
            misp.change_threat_level(event, 4)
    else:
        logger.info("No Event severity found")

    # Url of the original Alert
    if fireeye_alert.alert_url:
        misp.add_internal_link(event, fireeye_alert.alert_url, False, "Alert url: " +auto_comment)

    if fireeye_alert.alert_ma_id:
        misp.add_internal_text(event, fireeye_alert.alert_ma_id, False, "Alert ID "+auto_comment)


    # infos about the product detected it
    if fireeye_alert.product:
        if fireeye_alert.product == 'EMAIL_MPS' or fireeye_alert.product == 'Email MPS':
            misp.add_tag(event, "veris:action:social:vector=\"Email\"")
        elif fireeye_alert.product == 'Web MPS' or fireeye_alert.product == 'Web_MPS':
            misp.add_tag(event, "veris:action:malware:vector=\"Web drive-by\"")

    # if attack was by E-Mail
    if fireeye_alert.attacker_email:
        misp.add_email_src(event, fireeye_alert.attacker_email, False, auto_comment)

    if fireeye_alert.alert_src_domain:
        misp.add_domain(event,fireeye_alert.alert_src_domain,"Payload delivery",False,auto_comment)

    if fireeye_alert.mail_subject:
        misp.add_email_subject(event, fireeye_alert.mail_subject, False, auto_comment)
    if fireeye_alert.victim_email:
        misp.add_email_dst(event, fireeye_alert.victim_email, 'Payload delivery', False, auto_comment)
    if fireeye_alert.malware_md5:
        logger.debug("Malware within the event %s", fireeye_alert.malware_md5)
        misp.add_hashes(event, "Payload delivery", fireeye_alert.malware_file_name, fireeye_alert.malware_md5, None, None,
                        None, auto_comment, False)
    if fireeye_alert.malware_http_header:
        misp.add_traffic_pattern(event, fireeye_alert.malware_http_header, 'Network activity', False, auto_comment)
    if fireeye_alert.alert_src_ip:
        misp.add_target_machine(event, fireeye_alert.alert_src_ip, False, auto_comment, None)


    if fireeye_alert.root_infection:
        misp.add_internal_comment(event,fireeye_alert.root_infection,False,"Root infection",None)

    if fireeye_alert.smtp_header:
        misp.add_internal_text(event,fireeye_alert.smtp_header,False,"smtp_header "+auto_comment)

        from email import parser
        msg = parser.Parser().parsestr(fireeye_alert.smtp_header, headersonly=True)

        print("asd")

        if 'From' in msg:
            logger.debug(msg['From'])
            misp.add_email_src(event,msg['From'],False,"From: "+auto_comment)
        if 'To' in msg:
            logger.debug(msg['To'])
            misp.add_email_dst(event,msg['To'],False,"From: "+auto_comment)




    if fireeye_alert.alert_src_url:
        misp.add_url(event, fireeye_alert.alert_src_url,'Payload delivery',False,auto_comment)


    if fireeye_alert.dst_ip:
        misp.add_ipdst(event, fireeye_alert.dst_ip, 'Network activity', True, "Destination IP " + auto_comment, None)

    if fireeye_alert.dst_mac:
        misp.add_traffic_pattern(event, fireeye_alert.dst_mac, 'Network activity', True, "Dst Mac " + auto_comment, None)

    if fireeye_alert.dst_port:
        misp.add_traffic_pattern(event, fireeye_alert.dst_port, 'Network activity', True, "Dst Port " + auto_comment,
                                 None)

    if fireeye_alert.alert_src_host:
        misp.add_target_machine(event, fireeye_alert.alert_src_host, False, auto_comment, None)

        # TODO: check that
        # import sys
        # sys.path.insert(0, './ldap-query')

        from ldap_query import search_host_and_fqdn
        OS = search_host_and_fqdn(fireeye_alert.alert_src_host, 'operatingSystem')
        description = search_host_and_fqdn(fireeye_alert.alert_src_host, 'description')

        logger.debug("Searching for %s result %s", fireeye_alert.alert_src_host, OS)
        misp.add_internal_comment(event, OS, False, "OS of " + fireeye_alert.alert_src_host + auto_comment)
        misp.add_internal_text(event, description, False,
                               "description of " + fireeye_alert.alert_src_host + auto_comment)

    # TODO: this is not finished yet
    if fireeye_alert.c2services:
        misp.add_domain(event, fireeye_alert.c2_address, 'Network activity', True, auto_comment, None)
        misp.add_domain(event, fireeye_alert.c2_address, 'Network activity', True, auto_comment, None)
        misp.add_ipdst(event, fireeye_alert.c2_address, 'Network activity', True, "C2 IP " + auto_comment, None)
        misp.add_traffic_pattern(event, fireeye_alert.c2_port, 'Network activity', True, "C2 Port " + auto_comment, None)
        misp.add_traffic_pattern(event, fireeye_alert.c2_protocoll, 'Network activity', True, "C2 Protocoll " + auto_comment, None)


def main():
    """
    Main method of the tool.

    Args:
        -

    Raises:
        -

    """

    if not HAVE_PYMISP:
        logger.log('error', "Missing dependency, install pymisp (`pip install pymisp`)")
        return


    server = ThreadedHTTPServer((firemisp_ip, firemisp_port), \
									MyRequestHandler)
    logger.info("Starting HTTP server %s %s",firemisp_ip,firemisp_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.error("HTTP Server stopped")


if __name__ == "__main__":

    misp = init_misp(misp_url, misp_key)

    #clean the database for test purposes
    '''for i in range (1300,1388,1):
        misp.delete_event(i)
    exit()
    '''

    logging.basicConfig(level=logging.WARNING,
                        filename=firemisp_logfile,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    main()
