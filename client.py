import json
import copy
import os
import logging

from graphqlclient import GraphQLClient


log = logging.getLogger('bonfire.client')


ENVS_QUERY = """
{
  envs: environments_v1 {
    name
    parameters
    namespaces {
      name
    }
  }
}
"""

SAAS_QUERY = """
{
  saas_files: saas_files_v1 {
    name
    app {
      name
      parentApp {
        name
      }
    }
    parameters
    resourceTemplates {
      name
      path
      url
      parameters
      targets {
        namespace {
          name
        }
        ref
        parameters
      }
    }
  }
}
"""


class Client:
    def __init__(self, url):
        self.client = GraphQLClient(url)

        if "GRAPHQL_CREDS" in os.environ:
            self.client.inject_token(os.environ["GRAPHQL_CREDS"])

    def get_env(self, env):
        """Get insights env configuration."""
        for env_data in json.loads(self.client.execute(ENVS_QUERY))["data"]["envs"]:
            if env_data["name"] == env:
                env_data["namespaces"] = set(n["name"] for n in env_data["namespaces"])
                break
        else:
            raise ValueError(f"cannot find env '{env}'")

        return env_data

    def get_saas_files(self, app):
        """Get app's saas file data."""
        saas_files = []

        for saas_file in json.loads(self.client.execute(SAAS_QUERY))["data"]["saas_files"]:
            if saas_file["app"]["name"] != app:
                continue

            if saas_file["app"].get("parentApp", {}).get("name") != "insights":
                log.warning("ignoring app named '%s' that does not have parentApp 'insights'")
                continue

            # load the parameters as a dict to save us some trouble later on...
            saas_file['parameters'] = json.loads(saas_file['parameters'] or '{}')
            saas_files.append(saas_file)

        if not saas_files:
            raise ValueError(f"no saas files found for app '{app}'")
        return saas_files

    @staticmethod
    def get_filtered_resource_templates(saas_file_data, env_data):
        """Return resourceTemplates with targets filtered only to those mapped to 'env_name'."""
        resource_templates = {}

        for r in saas_file_data["resourceTemplates"]:
            name = r["name"]
            targets = []
            for t in r["targets"]:
                if t["namespace"]["name"] in env_data["namespaces"]:
                    targets.append(t)

            resource_templates[name] = copy.deepcopy(r)
            resource_templates[name]['targets'] = targets
            # load the parameters as a dict to save us some trouble later on...
            resource_templates[name]['parameters'] = json.loads(r['parameters'] or '{}')
            for t in resource_templates[name]['targets']:
                t['parameters'] = json.loads(t['parameters'] or '{}')

        return resource_templates