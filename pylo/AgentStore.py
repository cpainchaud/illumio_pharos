import pylo
from pylo import log
from .Helpers import *
import re


version_regex = re.compile(r"^(?P<major>[0-9]+)\.(?P<middle>[0-9]+)\.(?P<minor>[0-9]+)-(?P<build>[0-9]+)(u[0-9]+)?$")


class VENAgent(pylo.ReferenceTracker):

    def __init__(self, href: str, owner: 'pylo.AgentStore', workload: 'pylo.Workload' = None):
        pylo.ReferenceTracker.__init__(self)
        self.href = href
        self.owner = owner
        self.workload = workload

        self.version_string = None
        self.version_major = 0
        self.version_middle = 0
        self.version_minor = 0
        self.version_build = 0

        self.raw_json = None

    def load_from_json(self, data):
        self.raw_json = data

        status_json = data.get('status')
        if status_json is None:
            raise pylo.PyloEx("Cannot find VENAgent status in JSON from '{}'".format(self.href))

        self.version_string = status_json.get('agent_version')
        if self.version_string is None:
            raise pylo.PyloEx("Cannot find VENAgent version from '{}'".format(self.href))

        match = version_regex.match(self.version_string)

        if match is None:
            raise pylo.PyloEx("Invalid agent release version format '{}' from '{}'".format(self.version_string, self.href))

        self.version_major = int(match.group('major'))
        self.version_middle = int(match.group('middle'))
        self.version_minor = int(match.group('minor'))
        self.version_build = int(match.group('build'))



class AgentStore:

    def __init__(self, owner: 'pylo.Organization'):
        self.owner = owner
        self.itemsByHRef = {}  # type: dict[str,pylo.VENAgent]

    def find_by_href_or_die(self, href: str):

        find_object = self.itemsByHRef.get(href)
        if find_object is None:
            raise pylo.PyloEx("Agent with ID {} was not found".format(href))

        return find_object

    def create_venagent_from_workload_record(self, workload: 'pylo.Workload', json_data):
        href = json_data.get('href')
        if href is None:
            raise pylo.PyloEx("Cannot extract Agent href from workload '{}'".format(workload.href))

        agent = pylo.VENAgent(href, self, workload)
        agent.load_from_json(json_data)

        self.itemsByHRef[href] = agent

        return agent


    def count_agents(self):
        """

        :rtype: int
        """
        return len(self.itemsByHRef)



