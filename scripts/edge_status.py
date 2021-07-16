import copy
import datetime
import json
import re

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()


class magnum_cache:
    def __init__(self, **kwargs):

        self.nature = "mag-1"
        self.cluster_ip = None
        self.edge_matches = []

        for key, value in kwargs.items():

            if ("host" in key) and value:
                self.host = value

            if ("nature" in key) and value:
                self.nature = value

            if ("cluster_ip" in key) and value:
                self.cluster_ip = value

            if ("edge_matches" in key) and value:
                self.edge_matches.extend(value)

        self.cache_url = "http://{}/proxy/insite/{}/api/-/model/magnum/{}".format(self.insite, self.nature, self.cluster_ip)

        self.catalog_cache()

    def cache_fetch(self):

        try:

            login = {"username": "admin", "password": "admin"}

            response = requests.post(
                "https://%s/api/v1/login" % self.insite,
                headers={"Content-Type": "application/json"},
                data=json.dumps(login),
                verify=False,
                timeout=30.0,
            ).json()

            otbt = {"otbt-is": response["otbt-is"]}

            response = requests.get(self.cache_url, params=otbt, verify=False, timeout=30.0)
            response.close()

            return json.loads(response.text)

        except Exception as e:

            with open("edge_status", "a+") as f:
                f.write(str(datetime.datetime.now()) + " --- " + "magnum_cache_builder" + "\t" + str(e) + "\r\n")

            return None

    def catalog_cache(self):

        cache = self.cache_fetch()

        if cache:

            self.ipg_db = {}

            for device in cache["magnum-controlled-devices"]:

                if device["device"] in self.edge_matches:

                    edge_template = {
                        "s_device_name": device["device-name"],
                        "s_device": device["device"],
                        "s_device_size": device["device-size"],
                        "s_device_type": device["device-type"],
                        "s_control_address": device["control-1-address"]["host"],
                    }

                    self.ipg_db.update({edge_template["s_control_address"]: edge_template})


class status_collector(magnum_cache):
    def __init__(self, **kwargs):

        self.verbose = None
        self.catalog_results = {}
        self.insite = None
        self.collection = "latest"
        self.sdvn_natures = {}
        self.annotate = None
        self.suppress_severity = []
        self.suppress_known_issues = []

        self.severity = {
            "none": 0,
            "info": 1,
            "minor": 2,
            "medium": 3,
            "major": 4,
            "critical": 5,
        }

        for key, value in kwargs.items():

            if "verbose" in key and value:
                self.verbose = True

            if "disconnected" in key and value:
                self.disconnected = True

            if "sdvn_natures" in key and value:

                for nature in value:
                    self.sdvn_natures.update({nature: {"url": None}})

            if "insite" in key and value:
                self.insite = value

            if "override" in key and value:
                self.collection = value

            if "suppress_severity" in key and value:

                self.suppress_severity.extend(value)

                for severity in value:

                    if severity in self.severity.keys():
                        self.severity[severity] = 0

            if "suppress_known_issues" in key and value:
                self.suppress_known_issues.extend(value)

            if key == "annotate":

                exec("from {} import {}".format(value["module"], value["dict"]), globals())

                self.annotate = eval(value["dict"] + "()")

            if "annotate_db" in key:
                self.annotate = value

        if "magnum_cache" in kwargs.keys():
            magnum_cache.__init__(self, **kwargs["magnum_cache"])

        for nature, parts in self.sdvn_natures.items():

            parts["url"] = "https://{}/proxy/insite/{}/api/-/model/devices?collection={}".format(
                self.insite, nature, self.collection
            )

    def logon(self, http_session=requests):

        try:

            logon_params = {"username": "admin", "password": "admin"}
            url = "https://{}/api/v1/login".format(self.insite)

            resp = http_session.post(
                url,
                headers={"Content-Type": "application/json;charset=UTF-8"},
                data=json.dumps(logon_params),
                verify=False,
            )

            if "ok" in resp.text:
                return resp.status_code

        except Exception as e:
            print(e)

        return None

    def logout(self, http_session=requests):

        try:

            url = "https://{}/api/v1/logout".format(self.insite)

            resp = http_session.post(
                url,
                headers={"Content-Type": "application/json;charset=UTF-8"},
                verify=False,
            )

            return resp.status_code

        except Exception as e:
            print(e)

    def state_fetch(self, url, http_session=requests):

        try:

            response = http_session.get(url, verify=False, timeout=30.0)

            return json.loads(response.text)

        except Exception as e:

            with open("edge_status", "a+") as f:
                f.write(str(datetime.datetime.now()) + " --- " + "state_fetch" + "\t" + str(e) + "\r\n")

            return None

    @property
    def collect(self):

        state_db = {}
        documents = []

        with requests.Session() as http_session:

            if self.logon(http_session):

                # iterate through dictonary of natures and get the name and url key
                for nature, parts in self.sdvn_natures.items():

                    state = self.state_fetch(parts["url"], http_session)

                    if isinstance(state, dict):

                        # merge the state list into a nested tree of the nature name
                        if "devices" in state.keys():
                            state_db.update({nature: {"devices": state["devices"]}})

                summary_overall = {
                    "none": 0,
                    "info": 0,
                    "medium": 0,
                    "minor": 0,
                    "major": 0,
                    "critical": 0,
                    "type": "summary",
                }

                # iterate through each nature tree and then traverse each device
                for nature, devices in state_db.items():

                    nature_summary = {
                        "none": 0,
                        "info": 0,
                        "medium": 0,
                        "minor": 0,
                        "major": 0,
                        "critical": 0,
                        "type": "summary",
                    }

                    for device in devices["devices"]:

                        # only support the device if it's in the magnum db.
                        if device["host"] in self.ipg_db.keys():

                            # load in the device meta from the magnum db based on the device ip
                            # used as a key in the ipg_db cache from the magnum config
                            fields = copy.deepcopy(self.ipg_db[device["host"]])

                            # load in information on the severity of the device
                            fields.update(
                                {
                                    "s_status_descr": device["status"]["issue-level-highest"],
                                    "s_status_color": device["status"]["issue-level-highest-label-color"],
                                    "i_num_issues": 0,
                                    "i_severity_code": 0,
                                    "i_sort_weight": 0,
                                    "s_nature": nature,
                                    "s_type": "status",
                                }
                            )

                            # update severity code if description exists in dictionary
                            if fields["s_status_descr"] in self.severity.keys():
                                fields["i_severity_code"] = self.severity[fields["s_status_descr"]]

                            # generate url to access the device panel in the state collector
                            panel_url = (
                                "https://{}/proxy/insite/{}/device/{}?deviceview=Device&view=minimal&collection={}".format(
                                    self.insite, nature, device["host"].replace(".", "-"), self.collection
                                )
                            )

                            issue_url = (
                                "https://{}/proxy/insite/{}/device/{}?deviceview=Issues&view=minimal&collection={}".format(
                                    self.insite, nature, device["host"].replace(".", "-"), self.collection
                                )
                            )

                            fields.update({"s_panel_url": panel_url, "s_issue_url": issue_url})

                            # gray out the severity color if the suppressed severity if found in the suppression list
                            if fields["s_status_descr"] in self.suppress_severity:
                                fields["s_status_color"] = "rgba(170,170,170,1)"

                            ## need to get the issue if present OR if the severity is not in
                            ## the known severity list ##
                            if fields["s_status_descr"] != "none" and fields["s_status_descr"] not in self.suppress_severity:

                                # create a url based on the nature in the loop to get the device specific alerts
                                device_state_url = (
                                    "https://{}/proxy/insite/{}/api/-/model/device/{}/view/device/Issues?collection={}".format(
                                        self.insite, nature, device["host"], self.collection
                                    )
                                )

                                device_state = self.state_fetch(device_state_url, http_session)

                                if isinstance(device_state, dict):

                                    issues = []

                                    try:

                                        table = device_state["parts"][-1]["parts"][-1]

                                        for row in table["parts"]:
                                            if row["type"] == "row":

                                                try:

                                                    descr = row["parts"][1]["value"]

                                                    # try to remove any extra labeling in the issue description
                                                    if "on host " + device["host"] in descr:
                                                        issues.append(descr.split(" on host")[0])

                                                    elif "on " + device["host"] in descr:
                                                        issues.append(descr.split(" on " + device["host"])[0])

                                                    else:
                                                        issues.append(descr)

                                                except Exception as e:
                                                    print(e)
                                                    continue

                                        # remove issues from the list that are in the suppress configured list
                                        for issue in issues:

                                            if any(x in issue for x in self.suppress_known_issues):
                                                issues.remove(issue)

                                    except Exception:
                                        pass

                                    # new fields for information about the issues
                                    fields.update(
                                        {
                                            "i_num_issues": len(issues),
                                            "as_issue_list": issues,
                                        },
                                    )

                                    # create a new list of issues that are summarized. shrink down the list by removing input numbers.
                                    # shorten the issue desc by removing has or has an or is. remove temperature threshold value.
                                    delete_expressions = [
                                        r"[0-9]+\s",
                                        r"has an\s",
                                        r"has\s",
                                        r"\sis",
                                        r"\sgreater th[e,a]n degrees",
                                    ]

                                    summary_list = []
                                    for issue in issues:

                                        holder = issue
                                        for expression in delete_expressions:
                                            holder = re.sub(expression, "", holder)

                                        # try to group RX and TX seperate alerts together like "RX/TX"
                                        holder = re.sub(r"[R,T]X", "RX/TX", holder)

                                        summary_list.append(holder)

                                    # convert list to set to remove duplicates then back to a list > sorted
                                    fields.update({"as_summary_issues": sorted(list(set(summary_list)))})

                                    # create some weight to the issue to help sort ipgs based on their severity
                                    # and number of issues.  the below implies about maximum of 100 issues for this
                                    # to work properly
                                    fields["i_sort_weight"] = (fields["i_severity_code"] * 100) + fields["i_num_issues"]

                                    # update the date time to nicer readable string. in a try block because of some
                                    # unknowns with what date formats will be received or even if the date is there.
                                    try:

                                        fields.update({"s_issue_changed_date": device["marks"]["issue-changed-new-date"]})

                                        for dt_format in [
                                            "%Y-%m-%dT%H:%M:%S.%fZ",
                                            "%Y-%m-%dT%H:%M:%SZ",
                                        ]:

                                            try:

                                                dt = datetime.datetime.strptime(fields["s_issue_changed_date"], dt_format)

                                                # todo: make the time offset configurable for different system regions
                                                dt = dt - datetime.timedelta(hours=4)

                                                fields["s_issue_changed_date"] = dt.strftime("%b %d %H:%M:%S EST")

                                                break

                                            except Exception:
                                                continue

                                    except Exception:
                                        pass

                            # update the summarization dictionary
                            if fields["s_status_descr"] not in nature_summary.keys():
                                nature_summary.update({fields["s_status_descr"]: 1})

                            else:
                                nature_summary[fields["s_status_descr"]] += 1

                            # complete the annotations if there is a reference of information
                            if self.annotate:

                                if fields["s_device_name"] in self.annotate.keys():

                                    fields.update(self.annotate[fields["s_device_name"]])

                                    # create a terms list that lists which components the device belongs to.
                                    # it doesn't include the pcr name if there are other components, otherwise, the
                                    # pcr name is used. this terms list is used by the handlebars visulizer because it cannot
                                    # use the filters aggregation.
                                    term_list = []

                                    if len(self.annotate[fields["s_device_name"]].keys()) > 1:

                                        for key, value in self.annotate[fields["s_device_name"]].items():
                                            if key != "PCR":

                                                term_list.append(value)

                                    else:
                                        term_list.append(fields["PCR"])

                                    if len(term_list) > 0:
                                        fields.update({"as_terms": term_list})

                            # build the final device document with the full status and
                            # annotations
                            document = {
                                "fields": fields,
                                "host": device["host"],
                                "name": "statusmon",
                            }

                            documents.append(document)

                    # generate the nature summary doucment and then update the overall summary counters
                    document = {"fields": nature_summary, "host": nature, "name": "statusmon"}
                    documents.append(document)

                    for key, value in nature_summary.items():

                        if key not in summary_overall.keys():
                            summary_overall.update({key: value})

                        elif key != "type":
                            summary_overall[key] += value

                # complete the final overall summary document of all the natures
                document = {"fields": summary_overall, "host": self.insite, "name": "statusmon"}
                documents.append(document)

                if self.verbose:

                    print("IPG Cache: ", len(self.ipg_db.keys()))
                    print("documents: ", len(documents))

                self.logout(http_session)

        return documents


def main():

    params = {
        "sdvn_natures": ["sdvn-1"],
        "insite": "172.16.205.77",
        "override": "loaded",
        "verbose": True,
        "suppress_severity": ["info", "minor"],
        "suppress_known_issues": [
            "QSFP 3 RX Power",
            "QSFP 3 TX Power",
            "QSFP 4 RX Power",
            "QSFP 4 TX Power",
        ],
        "annotate": {"module": "ThirtyRock_PROD_edge_def", "dict": "return_reverselookup"},
        "magnum_cache": {
            "nature": "mag-1",
            "cluster_ip": "100.103.224.21",
            "edge_matches": ["570IPG-X19-25G", "3067VIP10G-3G"],
            # "edge_matches": ["3067VIP10G-3G"],
        },
    }

    collector = status_collector(**params)

    print(json.dumps(collector.collect, indent=2))


if __name__ == "__main__":
    main()
