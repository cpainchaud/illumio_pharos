import os
import sys
import argparse
import math
from datetime import datetime
from typing import Dict, List, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import pylo


# <editor-fold desc="Argparse stuff">
parser = argparse.ArgumentParser(description='TODO LATER', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--dev-use-cache', type=bool, nargs='?', required=False, default=False, const=True,
                    help='For developers only')

parser.add_argument('--host', type=str, required=True,
                    help='hostname of the PCE')
parser.add_argument('--debug', '-d', type=bool, nargs='?', required=False, default=False, const=True,
                    help='extra debugging messages for developers')
parser.add_argument('--verbose', '-v', type=bool, nargs='?', required=False, default=False, const=True,
                    help='')

# </editor-fold>


args = vars(parser.parse_args())

if args['debug']:
    pylo.log_set_debug()


hostname = args['host']
verbose = args['verbose']
use_cached_config = args['dev_use_cache']


now = datetime.now()
report_file = 'ven-duplicate-removal_{}.csv'.format(now.strftime("%Y%m%d-%H%M%S"))
report_file_excel = 'ven-duplicate-removal_{}.xlsx'.format(now.strftime("%Y%m%d-%H%M%S"))

csv_report_headers = ['name', 'hostname', 'role', 'app', 'env', 'loc', 'href', 'action']
csv_report = pylo.ArrayToExport(csv_report_headers)


# <editor-fold desc="PCE Configuration Download and Parsing">
org = pylo.Organization(1)
fake_config = pylo.Organization.create_fake_empty_config()

if use_cached_config:
    org.load_from_cache_or_saved_credentials(hostname)
else:
    print(" * Looking for credentials for PCE '{}'... ".format(hostname), end="", flush=True)
    connector = pylo.APIConnector.create_from_credentials_in_file(hostname, request_if_missing=True)
    print("OK!")

    print(" * Downloading Workloads/Agents listing from the PCE... ", end="", flush=True)
    fake_config['workloads'] = connector.objects_workload_get()
    print("OK!")

    print(" * Downloading Labels listing from the PCE... ", end="", flush=True)
    fake_config['labels'] = connector.objects_label_get()
    print("OK!")

    print(" * Parsing PCE data ... ", end="", flush=True)
    org.pce_version = connector.version
    org.connector = connector
    org.load_from_json(fake_config)
    print("OK!")

print(" * PCE data statistics:\n{}".format(org.stats_to_str(padding='    ')))
# </editor-fold>


all_workloads = org.WorkloadStore.itemsByHRef.copy()
used_filters = {}


def add_workload_to_report(wkl: pylo.Workload, action: str):
    labels = workload.get_labels_list()
    new_row = {
            'hostname': wkl.name,
            'role': labels[0],
            'app': labels[1],
            'env': labels[2],
            'loc': labels[3],
            'href': wkl.href,
            'action': action
    }

    csv_report.add_line_from_object(new_row)


class DuplicatedRecord:
    def __init__(self):
        self.offline = []
        self.online = []
        self.unamanaged= []

    def add_workload(self, wkl: pylo.Workload):
        if wkl.unmanaged:
            self.unamanaged.append(wkl)
            return
        if wkl.online:
            self.online.append(wkl)
            return
        self.offline.append(wkl)

    def count_workloads(self):
        return len(self.unamanaged) + len(self.online) + len(self.offline)

    def has_dupicates(self):
        if len(self.offline) + len(self.online) + len(self.unamanaged) > 1:
            return True
        return False


class DuplicateRecordManager:
    def __init__(self):
        self._records: Dict[str, DuplicatedRecord] = {}

    def count_record(self):
        return len(self._records)

    def count_workloads(self):
        total = 0
        for record in self._records.values():
            total += record.count_workloads()

    def records(self):
        return list(self._records.values())

    def count_duplicates(self):
        count = 0
        for record in self._records.values():
            if record.has_dupicates():
                count += 1
        return count

    def add_workload(self, wkl: pylo.Workload):
        lower_hostname = wkl.get_name_stripped_fqdn().lower()

        if lower_hostname not in self._records:
            self._records[lower_hostname] = DuplicatedRecord()
        record = self._records[lower_hostname]
        record.add_workload(wkl)


duplicated_hostnames = DuplicateRecordManager()

print(" * Looking for VEN with duplicated hostname(s)")

for workload in all_workloads.values():
    if workload.deleted:
        continue
    duplicated_hostnames.add_workload(workload)

print(" * Found {} duplicated hostnames".format(duplicated_hostnames.count_duplicates()))

for dup_hostname, dup_record in duplicated_hostnames._records.items():
    if not dup_record.has_dupicates():
        continue
    if verbose:
        print("  - hostname '{}' has duplicates. ({} online, {} offline, {} unmanaged)".format(dup_hostname,
                                                                                     len(dup_record.online),
                                                                                     len(dup_record.offline),
                                                                                     len(dup_record.unamanaged)))



print()
print(" * Writing report file '{}' ... ".format(report_file), end='', flush=True)
csv_report.write_to_csv(report_file)
print("DONE")
print(" * Writing report file '{}' ... ".format(report_file_excel), end='', flush=True)
csv_report.write_to_excel(report_file_excel)
print("DONE")

if csv_report.lines_count() < 1:
    print("\n** WARNING: no entry matched your filters so reports are empty !\n")


