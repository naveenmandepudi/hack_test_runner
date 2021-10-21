import getopt
import os
import subprocess
import sys
from textwrap import dedent
import pandas as pd
import numpy as np
import re
import datetime
import yaml
import Utils

DEFAULT_TASK_WEIGHT = 1


def scriptentrypoint(yaml_location) -> None:
    """
    This is the entry point for script
    :return: None
    """
    print("am in")
    # argumentList = sys.argv[1:]
    # options = "i:"
    # long_options = ["input="]

    TIMESTAMP = str(datetime.datetime.now().strftime("%d%m%Y_%H%M%S"))
    print(TIMESTAMP)

    global row, code, rampdown_time_insecs, l_commands, user_input
    l_commands = ''
    try:
        # arguments, values = getopt.getopt(argumentList, options, long_options)
        # if len(arguments) == 0:
        #     sys.exit("No arguments given hence terminated!!")
        # for currentArgument, currentValue in arguments:
        #     if currentArgument in ("-i", "--input"):
        #         yaml_location = currentValue
        #     else:
        #         sys.exit("[ERROR] Please provide valid config file!!")
        read_yaml(yaml_location)
        user_input = config['user_input']['api_data']
        is_run_locust = config['user_input']['start_test']
        app_name = config['user_input']['app_name']
        is_sf_auth = True if config['user_input']['user_auth_type'].lower() == "salesforce" else False
        l_commands += " -u " + str(config['locust_commands']['users']) if config['locust_commands'][
            'users'] else sys.exit(
            "Users count is mandatory!!")
        l_commands += " -r " + str(config['locust_commands']['rampup']) if config['locust_commands'][
            'rampup'] else sys.exit(
            "Rampup is mandatory!!")
        l_commands += " --host=" + config['locust_commands']['host'] if config['locust_commands'][
            'host'] else " --host=''"
        l_commands += " -t " + config['locust_commands']['runtime'] if config['locust_commands'][
            'runtime'] else sys.exit(
            "Test execution time is mandatory!!")
        rampdown_time_insecs = int(config['locust_commands']['users']) * 2 if not config['locust_commands'][
            'rampdown'] else \
            config['locust_commands']['rampdown']

        # splunk_endpoint = config['reporting']['splunk_endpoint']
        # splunk_auth_key = config['reporting']['splunk_auth_key']
        # splunk_cert_path = config['reporting']['splunk_cert']

        # Adding CSV test data validations
        test_data_path = config['user_input']['test_data']['source']
        is_reuse_test_data = config['user_input']['test_data']['reuse_on_eof']
        requested_num_of_users = config['locust_commands']['users']
        is_test_data = False
        if test_data_path is not None and is_reuse_test_data is not None:
            if is_stage_defined:  # to-do validate for stage input
                requested_num_of_users = stage_max_users
            is_test_data = True
            validate_testdata = Utils.validate_test_data(reuse_data_on_eof=is_reuse_test_data,
                                                         test_data_path=test_data_path,
                                                         requested_num_of_users=requested_num_of_users)
            if not validate_testdata.csv_data():
                sys.exit("[ERROR] CSV row count is less than no of users needed for test execution!!")
            data_headers = validate_testdata.get_headers()


        # Adding CSV test data validations

        print("[INFO] Reading input from --> '%s'" % user_input)
        l_read_csv()
        code = driver().replace("#appname#", app_name) \
            # .replace("#splunk_endpoint#", splunk_endpoint) \
            # .replace("#splunk_auth_key#", splunk_auth_key) \
            # .replace("#splunk_cert_path#", '"' + l_set_certificate_reporting(splunk_cert_path) + '"')
        if is_test_data:
            code = code.replace("#Read datasource#",
                                update_datasoruce().format(test_data_path=os.path.abspath(test_data_path)))
        if is_sf_auth:
            code = code.replace("#on_start#", sf_auth()) \
                .replace("#login_soap_request_body#", '"""' + l_sf_login() + '"""')
            if is_test_data:
                code = code.replace("#sf_extra#", data_headers)
        else:
            if is_test_data:
                code = code.replace("#on_start#", non_sf_auth().format(headers=data_headers))
            else:
                pass
        if is_stage_defined:
            code = code + "\n" + l_loadshape().format(stage_data=str(stage_dict))

        for row in range(0, r):
            l_generate_task()
        l_write_locust_file(app_name)
        if is_run_locust:
            l_run_locust(app_name + "_" + TIMESTAMP)

    except getopt.error as err:
        print(str(err))


def driver():
    """
    driver function is the core function for generating locust file.
    It doesn't need any parameters
    """
    return dedent("""
        from locust import HttpUser, SequentialTaskSet, task, events, LoadTestShape
        import json
        import requests
        import xml.dom.minidom, re
        from html import escape
        import sys, Utils
        
        data = {}
        
        @events.init.add_listener
        def _(environment, **kwargs):
            @events.request.add_listener
            def _(**kw):
                data["active_users"] = environment.runner.user_count
        
        #Read datasource#
        class UserBehavior(SequentialTaskSet):

            #on_start#
            ### Additional tasks can go here ###
        
        class WebsiteUser(HttpUser):
        
            request_stats = [list()]
            
            def __init__(self, parent):
                super().__init__(parent)
                events.request.add_listener(self.hook_request_success)
                events.quitting.add_listener(self.hook_locust_quit)
            
            def hook_request_success(self, **kwargs):
                global data
                self.request_stats.append([kwargs])
                data["app_name"] = "#appname#"
                data["request_url"] = kwargs["context"]["url"] if kwargs["context"] else ""
                data["framework"] = "Locust"
                data["assertion_msg"] = str(kwargs["exception"])               
                for arg in kwargs:
                    if arg not in ["exception","response","response_time","context"] :
                        data[arg] = kwargs[arg]
                    elif arg == "response":
                        data["response_code"] = re.findall(r'\d+', str(kwargs[arg]))[0]
                    elif arg == "response_time":
                        data[arg] = round(kwargs[arg],2)
                data["others"] = {}  # placeholder for future data
                # requests.post(url="#splunk_endpoint#",
                #               data=json.dumps(data),
                #               headers={"AUTHORIZATION": "Splunk #splunk_auth_key#"},
                #               verify=#splunk_cert_path#)
            
            def save_success_stats(self):
                import csv
                with open('success_req_stats.csv', 'w') as csv_file:
                    writer = csv.writer(csv_file)
                    for value in self.request_stats:
                        writer.writerow(value)
                print("csv pulled for all requests stats")
            
            def hook_locust_quit(self, **kwargs):
                # self.save_success_stats()
                print("[INFO] Test execution is over!!")
            tasks = [UserBehavior]
            min_wait = 1000
            max_wait = 3000
    """).strip()


def update_datasoruce():
    return dedent("""   
    pull_source_data = Utils.CSVReader(file='{test_data_path}', reuse=True)
    next(pull_source_data)  # to skip headers
    
    """)


def l_loadshape():
    """
    This is for shaping the load, called when loadTestShape class invoked
    :return: Class with substituted stage data
    """
    return dedent("""
    
    class StagesShape(LoadTestShape):
        stages = {stage_data}
    
        def tick(self):
            run_time = self.get_run_time()
    
            for stage in self.stages:
                if run_time < stage["duration"]:
                    tick_data = (stage["users"], stage["spawn_rate"])
                    return tick_data
    
            return None
    """)


def non_sf_auth():
    """
    Adds non sf based on_start and on_stop method code
    :return:
    """
    return dedent("""
        def __init__(self, parent):
                super().__init__(parent)
                
            def on_start(self):
                {headers}
    """).strip()


def sf_auth():
    """
    Used when salesforce auth is needed for any request
    :return: pre-defined 'on_start', 'on_stop' locust methods along with authentication handling methods
    """
    return dedent("""
        def __init__(self, parent):
                super().__init__(parent)
                self.sessionid = ""
                self.instance = ""
                self.headers = {
                    'Content-Type': 'application/json',
                    'X-PrettyPrint': '1',
                    'Accept': 'application/json'
                }
            def on_start(self):
                #sf_extra#
                self.sessionid, self.orgID, self.host = self.SalesforceLogin(username=self.username,password=self.password)
                self.headers["Authorization"] = "Bearer %s" % self.sessionid
        
            def SalesforceLogin(self,   
                                username=None,
                                password=None,
                                sf_version=49.0,
                                domain="test",
                                ):
                soap_url = 'https://{domain}.salesforce.com/services/Soap/u/{sf_version}'
                soap_url = soap_url.format(domain=domain,
                                           sf_version=sf_version)
                                           
                username = escape(username) if username else None
                password = escape(password) if password else None
        
                login_soap_request_headers = {
                    'content-type': 'text/xml',
                    'charset': 'UTF-8',
                    'SOAPAction': 'login'
                }
                
                login_soap_request_body = #login_soap_request_body#.format(username=username, password=password)
        
                try:
                    return self.soap_login(soap_url, login_soap_request_body,
                                       login_soap_request_headers)
                except AttributeError:
                    response = (requests).post(
                        soap_url, login_soap_request_body, headers=login_soap_request_headers)
                    sys.exit(self.getUniqueElementValueFromXmlString(
                        response.content, 'faultstring'))
        
            def soap_login(self,soap_url, request_body, headers, session=None):
                response = (session or requests).post(
                    soap_url, request_body, headers=headers)
        
                if response.status_code != 200:
                    print("[ERROR] Login failed!!")
        
                session_id = self.getUniqueElementValueFromXmlString(
                    response.content, 'sessionId')
                server_url = self.getUniqueElementValueFromXmlString(
                    response.content, 'serverUrl')
                organizationId = self.getUniqueElementValueFromXmlString(
                    response.content, 'organizationId')
                return session_id, organizationId, re.search('(\w+)://([\w\-\.]+)', server_url).group(0)
        
            def getUniqueElementValueFromXmlString(self, xmlString, elementName):
                xmlStringAsDom = xml.dom.minidom.parseString(xmlString)
                elementsByName = xmlStringAsDom.getElementsByTagName(elementName)
                elementValue = None
                if len(elementsByName) > 0:
                    elementValue = (
                        elementsByName[0]
                            .toxml()
                            .replace('<' + elementName + '>', '')
                            .replace('</' + elementName + '>', '')
                    )
                return elementValue
            
            def on_stop(self):
                self.client.get(url=self.host + "/secur/logout.jsp",
                                name="T_sf_logout",
                                context={"url":"/secur/logout.jsp"},
                                headers=self.headers)
        """).strip()


def l_sf_login():
    """
    Soap method for salesforce authentication
    :return: SOAP request
    """
    return dedent("""<?xml version="1.0" encoding="utf-8" ?>
            <soapenv:Envelope
                    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                    xmlns:urn="urn:partner.soap.sforce.com">
                <soapenv:Header>
                    <urn:CallOptions>
                        <urn:client>RestForce</urn:client>
                        <urn:defaultNamespace>sf</urn:defaultNamespace>
                    </urn:CallOptions>
                </soapenv:Header>
                <soapenv:Body>
                    <urn:login>
                        <urn:username>{username}</urn:username>
                        <urn:password>{password}</urn:password>
                    </urn:login>
                </soapenv:Body>
            </soapenv:Envelope>""").strip()


def l_task_description():
    """
    Invoked for each task to be added
    :return: added parameters and functional task
    """
    return dedent("""
                @task({weight})
                    def {name}(self):
                        with self.client.{method}(
                            catch_response=True,
                            headers={headers},
                            name="{name}",
                            url={url},
                            context={context},
                            {args}
                        ) as response:
                            if response.status_code >= 400:
                                response.failure('response code is >= 400')
                            ##checks##
                            else:
                                response.success()

                    ### Additional tasks can go here ###
    """).strip()


def add_string_validation(kw):
    """
    Validation for string type metrics like response.text
    :param kw: kw is used to determine whether validation is against response.text or json object
    :return:
    """

    if kw:
        return dedent("""
                elif {validatein} != {validate}:               
                                response.failure("{validatein} != {validate}")
                            ##checks##  
    """).strip()

    else:
        return dedent("""
                    elif "{validate}" not in {validatein}:
                                    response.failure("{validate} not found in {validatein}")
                                ##checks##  
        """).strip()


def add_nonstring_validation():
    """
    Validation for nonstring type metrics like sla
    :return:
    """
    return dedent("""
        elif response.elapsed.total_seconds() > {validate}:
                        response.failure("response.elapsed.total_seconds() > {validate}")
                    ##checks##
    """).strip()


def replace_last(string, find, replace):
    """
    Used to replace last occurance of a string
    :param string: Source string in which replace should happen
    :param find: String to be replaced
    :param replace: Replacing string
    :return: source string with replace operation
    """
    reversed = string[::-1]
    replaced = reversed.replace(find[::-1], replace[::-1], 1)
    return replaced[::-1]


def extraTask(task_data, source):
    """
    This is used to format each task with given parameters.
    :param task_data: Serialized object which contains parameters for the task description.
    :param source: The string/data where extra tasks to be added
    :return: locust file description
    """
    task = source.replace("### Additional tasks can go here ###", l_task_description().format(**task_data))

    if validations_custom:
        for k, v in validations_custom.items():
            if k not in ["sla"]:
                if str(v).find("=") == -1:
                    task = replace_last(task, "##checks##",
                                        add_string_validation(False).format(validatein="response.text", validate=v))
                elif str(v).find("=") != -1:
                    key, val = str(v).split("=")
                    key = re.sub(r"[\"]+", "'", key)
                    val = re.sub(r"[\"]+", "'", val)
                    # val = re.sub(r"[^\s0-9a-zA-Z]+", "", val)
                    # val = "'" + val + "'" if re.search(r'[a-zA-Z]+', val) else val
                    task = replace_last(task, "##checks##",
                                        add_string_validation(True).format(validatein="response.json()" + str(key),
                                                                           validate=val))
                else:
                    sys.exit("[ERROR] Invalid response validation given, hence exiting!!")
            else:
                task = replace_last(task, "##checks##",
                                    add_nonstring_validation().format(validate=v))

    return task


def l_generate_task():
    """
    Generates task data
    :return: None
    """
    global data, code, validations_custom, row
    data = {}
    validations_custom = {}
    for col in df.columns:
        if col == "weight" and pd.isna(df[col].values[row]):
            data[col] = int(DEFAULT_TASK_WEIGHT)
        if col.lower() == "postdata":
            if not pd.isna(df[col].values[row]):
                data["args"] = 'data=json.dumps(' + str(df[col].values[row]) + ')' + ","
            else:
                data["args"] = ""
        if col == "headers" and pd.isna(df[col].values[row]):
            data[col] = "self.headers"
        if not pd.isna(df[col].values[row]):
            if col == "url":
                url_val = df[col].values[row]
                host_present = len(re.findall('(\w+)://([\w\-\.]+)', url_val))
                if host_present == 0:
                    url_val = "self.host + " + '"' + url_val + '"'
                else:
                    url_val = '"' + url_val + '"'
                # substitute parameters
                for match in re.finditer('\${(.+?)}', url_val):
                    url_val = re.sub('\${(.+?)}', '" + self.' + match.group(1) + ' + "', url_val, 1)
                data[col] = url_val
                if re.search('^(self\.)', url_val):
                    data["context"] = '{"url":' + url_val + '}'
                else:
                    data["context"] = '{"url":"' + re.sub('"', "", url_val, 1) + '}'
            elif col == "headers":
                data[col] = df[col].values[row]
            elif col == "weight":
                data[col] = int(df[col].values[row])
            elif col == "sla":  # and not pd.isna(df[col].values[row])
                validations_custom[col] = df[col].values[row]
            elif col == "responsevalidation":  # and not pd.isna(df[col].values[row])
                validations_custom[col] = df[col].values[row]
            else:
                data[col] = df[col].values[row]
    code = extraTask(data, source=code)


def l_run_locust(htmlRpt):
    """
    Invoke when locust file ready for execution
    :param htmlRpt: locust html report name
    :return: None
    """

    global filename, l_commands, rampdown_time_insecs
    try:
        loc_args = 'locust -f ' + filename + ' --headless --only-summary --html ' \
                                             './TestReport_' + htmlRpt + '.html' + l_commands + ' --stop-timeout ' \
                   + str(rampdown_time_insecs)
        print("[INFO] Launching locust with the following command -> " + loc_args)
        subprocess.call(loc_args, shell=True)
    except:
        print("[ERROR] Something wrong with your locust file!")


def l_write_locust_file(appName):
    """
    Write locust code to a file
    :param appName: filename formatted to demo_DateMonthYear_HourMinuteSeconds
    :return: None
    """
    global filename
    appName = appName if appName else "AUT"
    filename = appName + "_" + str(datetime.datetime.now().strftime(
        "%d%m%Y_%H%M%S")) + ".py"  # filename formatted to demo_DateMonthYear_HourMinuteSeconds
    with open(filename, "w") as f:
        f.write(code)


def isNaN(num):
    return num != num


def l_read_csv():
    """
    Reads CSV using pandas library
    :return:
    """
    weights_arr = []
    global df, r, user_input
    weights_check = False
    try:
        df = pd.read_csv(user_input)
    except:
        sys.exit("[ERROR] Looks like API csv file is corrupted!!")
    for x in df['weight'].values:
        if isNaN(x):
            weights_check = True
            print("[WARNING] Empty weights will be given DEFAULT_TASK_WEIGHT=1")
            break
        else:
            weights_arr.append(int(x))

    if not weights_check:
        is_all_weights_zero = np.all((np.array(weights_arr) == 0))
        if is_all_weights_zero:
            sys.exit("[ERROR] At least one task should be given valid weight!!")
    r, c = df.shape


def l_set_certificate_reporting(cert_path):
    """
    For external communications those who needs cacert, this function will read cacerts from certs folder
    :return:
    """
    if cert_path:
        try:
            if os.path.isfile(os.path.abspath(cert_path)):
                return os.path.abspath(cert_path)
        except FileNotFoundError:
            sys.exit("Splunk certificate is not present in cert folder!!")
    else:
        for file in os.listdir(os.getcwd() + "/certs"):
            if file.endswith(".pem"):
                return os.getcwd() + "/certs/" + file


def read_yaml(yaml_path=None):
    """
    Read yaml file
    :param yaml_path: Path of the yaml file
    :return: None
    """
    global config, stage_dict, is_stage_defined, stage_max_users
    if not os.path.isfile(yaml_path):
        sys.exit("Provide valid config file!!")
    with open(yaml_path) as yml:
        config = yaml.full_load(yml)

    stage_dict = []
    stage_users_list = []
    is_stage_defined = True
    stage_shape = config['locust_commands']['stages']
    for k, v in stage_shape.items():
        stage_dict.append(stage_shape[k])
        try:
            stage_users_list.append(stage_shape[k]['users'])
        except TypeError:
            pass
    try:
        if set(stage_dict) == {None}:
            is_stage_defined = False
    except TypeError or AttributeError:
        stage_max_users = max(stage_users_list)


# if __name__ == "__main__":
#     scriptentrypoint()
