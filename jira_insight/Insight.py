import requests
from lazy import lazy
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import logging

from InsightObjectSchema import InsightObjectSchema


class Insight(object):
    def __init__(self, jira_url, auth, params=None):
        retries = 3
        backoff_factor = 0.3
        status_forcelist = (500, 502, 504)
        retry_session = None
        self.jira_url = jira_url
        self.insight_api_url = f"{jira_url}/rest/insight/1.0"
        self.auth = auth
        # Configure retry session
        self.retry_session = retry_session or requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.retry_session.mount("http://", adapter)
        self.retry_session.mount("https://", adapter)
        self.retry_session.auth = self.auth
        self.retry_session.params = params

    def __str__(self):
        return f"Insight: {self.jira_url}"

    @lazy
    def object_schemas(self):
        api_path = "/objectschema/list"
        object_schemas_json_request = self.do_api_request(api_path)
        object_schemas_json = object_schemas_json_request.get("objectschemas", {})
        object_schemas = {}
        logging.info("Loading object schemas")
        object_schemas_count = len(object_schemas_json)
        index = 1
        for object_schema_json in object_schemas_json:
            logging.info(
                f'Loading object schema {object_schema_json["name"]} ({index}/{object_schemas_count})'
            )
            object_schema_id = object_schema_json["id"]
            object_schemas[object_schema_id] = InsightObjectSchema(
                self, object_schema_id
            )
            index += 1

        return object_schemas

    def do_api_request(self, path, method="get", json=None, params=None):
        if method == "get":
            request = self.retry_session.get(self.insight_api_url + path, params=params)
            request.raise_for_status()
            return request.json()
        elif method == "post":
            request = self.retry_session.post(
                self.insight_api_url + path, json=json, params=params
            )
            request.raise_for_status()
            return request.json()
        elif method == "head":
            request = self.retry_session.head(
                self.insight_api_url + path, params=params
            )
            request.raise_for_status()
            return request.json()
        else:
            raise NotImplementedError
