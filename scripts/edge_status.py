import copy
import datetime
import json

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

        self.cache_url = "http://{}/proxy/insite/{}/api/-/model/magnum/{}".format(
            self.insite, self.nature, self.cluster_ip
        )

        self.catalog_cache()

    def cache_fetch(self):

        try:

            response = requests.get(self.cache_url, verify=False, timeout=30.0)

            return json.loads(response.text)

        except Exception as e:

            with open("edge_status", "a+") as f:
                f.write(
                    str(datetime.datetime.now())
                    + " --- "
                    + "magnum_cache_builder"
                    + "\t"
                    + str(e)
                    + "\r\n"
                )

            return None

    def catalog_cache(self):

        cache = self.cache_fetch()

        if cache:

            self.ipg_db = {}

            for device in cache["magnum"]["magnum-controlled-devices"]:

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

    def state_fetch(self, url):

        try:

            response = requests.get(url, verify=False, timeout=30.0)

            return json.loads(response.text)

        except Exception as e:

            with open("edge_status", "a+") as f:
                f.write(
                    str(datetime.datetime.now()) + " --- " + "state_fetch" + "\t" + str(e) + "\r\n"
                )

            return None

    @property
    def collect(self):

        state_db = {}

        # iterate through dictonary of natures and get the name and url key
        for nature, parts in self.sdvn_natures.items():

            state = self.state_fetch(parts["url"])

            if isinstance(state, dict):

                # merge the state list into a nested tree of the nature name
                if "devices" in state.keys():
                    state_db.update({nature: {"devices": state["devices"]}})

        documents = []

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
                    panel_url = "https://{}/proxy/insite/{}/device/{}?deviceview=Device&view=minimal&collection={}".format(
                        self.insite, nature, device["host"].replace(".", "-"), self.collection
                    )

                    fields.update({"s_panel_url": panel_url})

                    # gray out the severity color if the suppressed severity if found in the suppression list
                    if fields["s_status_descr"] in self.suppress_severity:
                        fields["s_status_color"] = "rgba(170,170,170,1)"

                    ## need to get the issue if present OR if the severity is not in
                    ## the known severity list ##
                    if (
                        fields["s_status_descr"] != "none"
                        and fields["s_status_descr"] not in self.suppress_severity
                    ):

                        # create a url based on the nature in the loop to get the device specific state to know
                        # what the full issue is.
                        device_state_url = "https://{}/proxy/insite/{}/api/-/model/device/{}?collection={}".format(
                            self.insite, nature, device["host"], self.collection
                        )

                        device_state = self.state_fetch(device_state_url)

                        if isinstance(device_state, dict):

                            issues = []

                            # iterate through the "values" to find the issues
                            for _, params in device_state["values"].items():

                                # append issues to the list if the status object exists in the key list
                                # OR if the name key (issue label) is not in the issue list.
                                if (
                                    "status" in params.keys()
                                    and params["name"] not in self.suppress_known_issues
                                ):

                                    if params["name"] not in issues:
                                        issues.append(params["name"])

                            # new fields for information about the issues
                            fields.update(
                                {
                                    "i_num_issues": len(issues),
                                    "s_issues": ", ".join(issues),
                                    "as_issue_list": issues,
                                },
                            )

                            # create some weight to the issue to help sort ipgs based on their severity
                            # and number of issues.  the below implies about maximum of 100 issues for this
                            # to work properly
                            fields["i_sort_weight"] = (fields["i_severity_code"] * 100) + fields[
                                "i_num_issues"
                            ]

                            # update the date time to nicer readable string. in a try block because of some
                            # unknowns with what date formats will be received or even if the date is there.

                            for date_key in ["issue-changed-new-date", "parameter-date-end"]:

                                try:

                                    fields.update(
                                        {"s_issue_changed_date": device_state["marks"][date_key]}
                                    )

                                    for dt_format in [
                                        "%Y-%m-%dT%H:%M:%S.%fZ",
                                        "%Y-%m-%dT%H:%M:%SZ",
                                    ]:

                                        try:

                                            dt = datetime.datetime.strptime(
                                                fields["s_issue_changed_date"], dt_format
                                            )

                                            dt = dt - datetime.timedelta(hours=4)

                                            fields["s_issue_changed_date"] = dt.strftime(
                                                "%b %d %H:%M:%S EST"
                                            )

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

        return documents


def main():

    params = {
        "sdvn_natures": ["sdvn-ipg", "sdvn-2"],
        "insite": "172.16.205.201",
        "override": "loaded",
        "verbose": True,
        "suppress_severity": ["info"],
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
        },
    }

    collector = status_collector(**params)

    print(json.dumps(collector.collect, indent=2))


if __name__ == "__main__":
    main()
