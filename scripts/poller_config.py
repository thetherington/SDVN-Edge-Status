import json
from edge_status import status_collector
from insite_plugin import InsitePlugin


class Plugin(InsitePlugin):
    def can_group(self):
        return False

    def fetch(self, hosts):

        try:

            self.collector

        except Exception:

            from ThirtyRock_PROD_edge_def import return_reverselookup

            params = {
                "sdvn_natures": ["sdvn-ipg"],
                "insite": "172.16.205.201",
                "annotate_db": return_reverselookup(),
                "magnum_cache": {
                    "nature": "mag-1",
                    "cluster_ip": "100.103.224.21",
                    "edge_matches": ["570IPG-X19-25G", "3067VIP10G-3G"],
                },
            }

            self.collector = status_collector(**params)

        return json.dumps(self.collector.collect)
