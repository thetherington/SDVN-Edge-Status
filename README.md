# SDVN Edge Status Health Collector

The purpose of this script module is to discover edge devices from the inSITE SDVN State collector and collect and index the status severity and issues, detected.  This module uses the Magnum SDVN configuration to get all known devices of a particular type(s) and queries the SDVN State collector API to get the current health and active issues.  This information is indexed together to be easily displayed and searched from a dashboard program.

Below are the module distinct abilities and features that it provides:

1. Supports device type(s) group lookup in Magnum SDVN.
2. Supports multiple SDVN State collectors.
3. Summarizing alerts for device.
4. Overall summary status of SDVN collectors and system.
5. Supports custom control room annotations definition (_if one exists_)

## Minimum Requirements:

- inSITE Version 11.0
- Python3.7 (_already installed on inSITE machine_)
- Python3 Requests library (_already installed on inSITE machine_)

## Installation:

Installation of the status monitoring module requires copying two scripts into the poller modules folder:

1. Copy __edge_status.py__ script to the poller python modules folder:
   ```
    cp scripts/edge_status.py /opt/evertz/insite/parasite/applications/pll-1/data/python/modules/
   ```

2. Restart the poller application

## Configuration:

To configure a poller to use the module start a new python poller configuration outlined below

1. Click the create a custom poller from the poller application settings page
2. Enter a Name, Summary and Description information
3. Enter the inSITE Server IP in the _Hosts_ tab
4. From the _Input_ tab change the _Type_ to __Python__
5. From the _Input_ tab change the _Metric Set Name_ field to __ipg__
6. From the _Input_ tab change the _Freqency_ value to __300000__ (_5 minutes_)
7. From the _Python_ tab select the _Advanced_ tab and enable the __CPython Bindings__ option
8. Select the _Script_ tab, then paste the contents of __scripts/poller_config.py__ into the script panel.

9. Update the below argument with the correct Magnum SDVN Cluster IP address and inSITE Nature name.  Update the _edge_matches_ argument with the edge type device type labels to be collected.

```
                "magnum_cache": {
                    "nature": "mag-1",
                    "cluster_ip": "100.103.224.21",
                    "edge_matches": ["570IPG-X19-25G", "3067VIP10G-3G"],
                },
```

10.  Save changes, then restart the poller program.

__Optional Parameters / Configuration__

11. The script module supports a setting to suppress any severities that are matched. this can be useful to mask certain severities from the dashboard program, and not further hae the script module collect alerts for the device.  Below is the option and argument to be enable and configured:

```
                "suppress_severity": ["info", "minor"]
```

12. The script module can also be configured with a list of alerts descriptions to skip over and not be indexed. these could be descriptions of alerts that are constant in the system. Below is the option and argument to be enabled and configured:

```
                "suppress_known_issues": [
                    "QSFP 3 RX Power",
                    "QSFP 3 TX Power",
                    "QSFP 4 RX Power",
                    "QSFP 4 TX Power",
                ],
```

13. The script module can collect status information from multiple collectors in the system. To do this, update the below option with additional collector names.

```
                "sdvn_natures": ["sdvn-1"],
```

14. It's possible for the script module to collect information from the SDVN State collector by a preloaded snapshot. This is useful for testing.  To do this, enable the below option:

```
                "override": "loaded"
```

15. (Optional) Locate the sections that import a custom control room definition file (_if available_) and uncomment the lines.

   ```
            # control room annotation file
            from ThirtyRock_PROD_edge_def import return_roomlist
   ```

   ```
                "annotate_db": return_reverselookup(),
            }
   ```

## Testing:

The edge_status script can be ran manually from the shell using the following command

```
python edge_status.py
```

You can configure the script with custom settings via the below dictionary definition:

```
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
```

Below is a sample output:

```
[
  {
    "fields": {
      "s_device_name": "3N.IPG.041.B.05",
      "s_device": "570IPG-X19-25G",
      "s_device_size": "8x8",
      "s_device_type": "edge",
      "s_control_address": "100.103.228.87",
      "s_status_descr": "medium",
      "s_status_color": "rgba(200,100,0,0.6)",
      "i_num_issues": 9,
      "i_severity_code": 3,
      "i_sort_weight": 309,
      "s_nature": "sdvn-1",
      "s_type": "status",
      "s_panel_url": "https://172.16.205.77/proxy/insite/sdvn-1/device/100-103-228-87?deviceview=Device&view=minimal&collection=loaded",
      "s_issue_url": "https://172.16.205.77/proxy/insite/sdvn-1/device/100-103-228-87?deviceview=Issues&view=minimal&collection=loaded",
      "as_issue_list": [
        "FPGA temperature is greater then 50 degrees",
        "External Reference 2 type is unknown",
        "External Reference 2 status is none",
        "QSFP 3 transceiver is missing based on TX power",
        "QSFP 4 transceiver is missing based on TX power",
        "QSFP 4 has an abnormal amount of TX Errors",
        "QSFP 3 transceiver is missing based on RX power",
        "QSFP 4 transceiver is missing based on RX power",
        "CPU Temperature is greater than 50 degrees"
      ],
      "as_summary_issues": [
        "CPU Temperature",
        "External Reference status none",
        "External Reference type unknown",
        "FPGA temperature",
        "QSFP abnormal amount of RX/TX Errors",
        "QSFP transceiver missing based on RX/TX power"
      ]
    },
    "host": "100.103.228.87",
    "name": "statusmon"
  },
  {
    "fields": {
      "s_device_name": "3N.IPG.42.B.02",
      "s_device": "570IPG-X19-25G",
      "s_device_size": "0x16",
      "s_device_type": "edge",
      "s_control_address": "100.103.252.5",
      "s_status_descr": "minor",
      "s_status_color": "rgba(170,170,170,1)",
      "i_num_issues": 0,
      "i_severity_code": 0,
      "i_sort_weight": 0,
      "s_nature": "sdvn-1",
      "s_type": "status",
      "s_panel_url": "https://172.16.205.77/proxy/insite/sdvn-1/device/100-103-252-5?deviceview=Device&view=minimal&collection=loaded",
      "s_issue_url": "https://172.16.205.77/proxy/insite/sdvn-1/device/100-103-252-5?deviceview=Issues&view=minimal&collection=loaded"
    },
    "host": "100.103.252.5",
    "name": "statusmon"
  }
]
```

Below are the summarization documents that are auto generated:

```
[
  {
    "fields": {
      "none": 0,
      "info": 1,
      "medium": 213,
      "minor": 69,
      "major": 126,
      "critical": 0,
      "type": "summary"
    },
    "host": "sdvn-1",
    "name": "statusmon"
  },
  {
    "fields": {
      "none": 0,
      "info": 1,
      "medium": 213,
      "minor": 69,
      "major": 126,
      "critical": 0,
      "type": "summary"
    },
    "host": "172.16.205.77",
    "name": "statusmon"
  }
]
```