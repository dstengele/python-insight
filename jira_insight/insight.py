import logging
import os

import requests
from lazy import lazy
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
from urllib3 import Retry


class BearerAuth(AuthBase):
    """Sets a Bearer token for the request."""

    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r


class Insight:
    def __init__(
        self,
        jira_url,
        auth=None,
        params=None,
        webbrowser_auth=False,
        basic_auth=None,
        oauth_auth=None,
        token_auth=None,
        jsessionid_auth=None,
    ):
        retries = 3
        backoff_factor = 0.3
        status_forcelist = (500, 502, 504)
        retry_session = None
        self.jira_url = jira_url
        self.insight_api_url = f"{jira_url}/rest/insight/1.0"

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

        # Auth
        if basic_auth:
            self.retry_session.auth = basic_auth
            self.auth_type = "basic"
        elif oauth_auth:
            self.retry_session.auth = oauth_auth
            self.auth_type = "oauth"
        elif token_auth:
            self.retry_session.auth = BearerAuth(token_auth)
            self.auth_type = "token"
        elif webbrowser_auth:
            import browser_cookie3

            self.retry_session.cookies = browser_cookie3.load()
            self.auth_type = "cookie"
        elif jsessionid_auth:
            self.retry_session.cookies = requests.cookies.cookiejar_from_dict(
                {"JSESSIONID": jsessionid_auth}
            )
            self.auth_type = "jsessionid"
        elif auth:
            self.retry_session.auth = auth
            logging.warning(
                "auth parameter is deprecated. Please switch to using either basic_auth=, oauth_auth=, token_auth=, webbrowser_auth= or jsessionid_auth=."
            )
        else:
            raise Exception("No auth method defined.")

        self.retry_session.params = params

    @lazy
    def object_schemas(self):
        return self.get_object_schemas()

    def get_object_schemas(self):
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

    def __str__(self):
        return f"Insight: {self.jira_url}"

    def do_api_request(self, path, method="get", json=None, params=None):
        path = self.insight_api_url + path
        if method == "get":
            request = self.retry_session.get(path, params=params)
        elif method == "post":
            request = self.retry_session.post(path, json=json, params=params)
        elif method == "put":
            request = self.retry_session.put(path, json=json, params=params)
        elif method == "delete":
            request = self.retry_session.delete(path, json=json, params=params)
        elif method == "head":
            request = self.retry_session.head(path, params=params)
        else:
            raise NotImplementedError

        request.raise_for_status()
        return request.json()


class InsightObject:
    def __init__(self, insight, object_id, object_json=None):
        self.insight = insight
        self.id = object_id
        self.object_json = object_json
        if not self.object_json:
            self.object_json = self.insight.do_api_request(f"/object/{self.id}")
        self.name = self.object_json["label"]
        self.objecttype_id = self.object_json["objectType"]["id"]
        self.object_schema = self.insight.object_schemas[
            self.object_json["objectType"]["objectSchemaId"]
        ]

        self.attributes = {}
        for attribute_json in self.object_json["attributes"]:
            attribute_object = InsightObjectAttribute(
                self,
                attribute_json["objectTypeAttributeId"],
                attribute_json["objectAttributeValues"],
            )
            self.attributes[attribute_object.name] = attribute_object

        # Long ago, Insight used to return all attributes for an object, even if they were empty. But then everything
        # changed when the fire nation attacked.
        # Some time ago, the API was changed to only return the attributes with values instead of returning null for
        # empty attributes. This breaks stuff, so we extract the available attributes from the objecttype and show them
        # with a None value.
        object_type_attributes_json = self.insight.do_api_request(
            f"/objecttype/{self.objecttype_id}/attributes"
        )

        for attribute_json in object_type_attributes_json:
            attribute_id = attribute_json["id"]
            attribute_name = attribute_json["name"]
            if attribute_name in self.attributes.keys():
                continue
            self.attributes[attribute_name] = InsightObjectAttribute(
                self, attribute_json["id"], empty=True
            )

    def update_object(self, attributes: dict):
        attributes_json = []
        for attribute_id, value in attributes.items():
            if isinstance(value, list):
                value_list = [{"value": value_list_item} for value_list_item in value]
            else:
                value_list = [{"value": value}]
            entry = {
                "objectTypeAttributeId": attribute_id,
                "objectAttributeValues": value_list,
            }
            attributes_json.append(entry)
        request_body = {
            "objectTypeId": self.object_json["objectType"]["id"],
            "attributes": attributes_json,
        }
        response = self.insight.do_api_request(
            "/object/{}".format(self.id), method="put", json=request_body
        )

        return response

    def __str__(self):
        return f"InsightObject: {self.name}"


class InsightObjectAttribute:
    def __init__(self, insight_object, attribute_id, values_json=None, empty=False):
        self.insight_object = insight_object
        self.id = attribute_id
        self.object_type_attribute = (
            self.insight_object.object_schema.object_type_attributes[self.id]
        )
        self.name = self.object_type_attribute.name
        self.values_json = values_json
        self.empty = empty

    @lazy
    def value(self):
        if self.empty:
            return None
        if self.values_json is None:
            self.values_json = self.insight_object.object_schema.insight.do_api_request(
                f"/objectattribute/{self.id}"
            )

        if not self.values_json:
            return None

        if self.object_type_attribute.attribute_type in ["User", "Object", "Select"]:
            value = []
            for value_json in self.values_json:
                if self.object_type_attribute.attribute_type in ["User", "Select"]:
                    value.append(value_json.get("value", None))
                    continue
                if self.object_type_attribute.attribute_type == "Object":
                    insight_object = InsightObject(
                        self.insight_object.insight,
                        value_json["referencedObject"]["id"],
                    )
                    value.append(insight_object)
                    continue
            return value
        else:
            value_json = self.values_json[0]
            if self.object_type_attribute.attribute_type in [
                "Text",
                "URL",
                "Email",
                "Textarea",
                "Date",
                "Date Time",
            ]:
                return value_json.get("value", None)
            if self.object_type_attribute.attribute_type == "Status":
                return value_json.get("status", None)
            if self.object_type_attribute.attribute_type == "Integer":
                return int(value_json.get("value", None))
            if self.object_type_attribute.attribute_type == "Double":
                return float(value_json.get("value", None))
            if self.object_type_attribute.attribute_type == "Boolean":
                return value_json.get("value", "false") == "true"

    def __str__(self):
        return f"InsightObjectAttribute: {self.name}, Value: {self.value}"


class InsightObjectSchema:
    def __init__(self, insight, insight_id):
        self.insight = insight
        self.id = insight_id
        object_schema_json = insight.do_api_request(f"/objectschema/{insight_id}")
        self.name = object_schema_json.get("name", None)
        self.key = object_schema_json.get("objectSchemaKey", None)
        self.description = object_schema_json.get("description", None)

    @lazy
    def object_types(self):
        return self.get_object_types()

    def get_object_types(self):
        object_types_json = self.insight.do_api_request(
            f"/objectschema/{self.id}/objecttypes/flat"
        )
        object_types = {}
        for object_type in object_types_json:
            object_types[object_type["id"]] = InsightObjectType(
                self.insight, object_type["id"], object_type
            )
        return object_types

    @lazy
    def object_type_attributes(self):
        return self.get_object_type_attributes()

    def get_object_type_attributes(self):
        object_type_attributes_json = self.insight.do_api_request(
            f"/objectschema/{self.id}/attributes"
        )
        object_type_attributes = {}
        for object_type_attribute_json in object_type_attributes_json:
            object_type_attributes[
                object_type_attribute_json["id"]
            ] = InsightObjectTypeAttribute(self, object_type_attribute_json)
        return object_type_attributes

    def __str__(self):
        return f"InsightObjectSchema: {self.name} ({self.key})"

    def search_iql(self, iql=None):
        api_path = "/iql/objects"
        params = {
            "objectSchemaId": self.id,
            "resultPerPage": 500,
            "includeTypeAttributes": "true",
            "page": 1,
        }
        if iql is not None:
            params["iql"] = iql

        while True:
            search_results = self.insight.do_api_request(api_path, params=params)
            if search_results["pageSize"] == 0:
                return
            logging.info(f'Got page {params["page"]} of {search_results["pageSize"]}')
            objects_to_check: list = search_results["objectEntries"]

            for json_object in objects_to_check:
                yield InsightObject(self.insight, json_object["id"], json_object)

            # Get additional pages if necessary
            if params["page"] == search_results["pageSize"]:
                return

            params["page"] += 1

    def object_exists(self, object_id):
        return (
            self.insight.do_api_request(f"/object/{object_id}", "head").status_code
            == 200
        )


class InsightObjectType:
    def __init__(self, insight, insight_id, object_type_json=None):
        self.insight = insight
        self.id = insight_id
        logging.info(f"Loading Insight object type with ID {insight_id}")
        if not object_type_json:
            object_type_json = self.insight.do_api_request(f"/objecttype/{insight_id}")
        self.name = object_type_json.get("name", None)
        self.object_schema_id = object_type_json.get("objectSchemaId", None)

    def get_object_type_attributes(self):
        object_type_attributes_json = self.insight.do_api_request(
            f"/objecttype/{self.id}/attributes"
        )
        object_type_attributes = {}
        for object_type_attribute_json in object_type_attributes_json:
            object_type_attributes[
                object_type_attribute_json["id"]
            ] = InsightObjectTypeAttribute(self, object_type_attribute_json)
        return object_type_attributes

    def __str__(self):
        return f"InsightObjectType: {self.name}"

    def create_object(self, attributes: dict):
        attributes_json = []
        for attribute_id, value in attributes.items():
            entry = {
                "objectTypeAttributeId": attribute_id,
                "objectAttributeValues": [{"value": value}],
            }
            attributes_json.append(entry)
        request_body = {"objectTypeId": self.id, "attributes": attributes_json}
        response = self.insight.do_api_request(
            "/object/create", method="post", json=request_body
        )
        object_id = response["id"]
        created_object = InsightObject(self.insight, object_id)
        return created_object


class InsightObjectTypeAttribute:
    def __init__(self, object_schema, object_type_attribute_json):
        self.insight = object_schema.insight
        self.object_schema = object_schema

        self.id = object_type_attribute_json["id"]
        self.name = object_type_attribute_json["name"]
        self.description = object_type_attribute_json.get("description", None)

        self.ATTRIBUTE_TYPES = {
            0: {
                0: "Text",
                1: "Integer",
                2: "Boolean",
                3: "Double",
                4: "Date",
                5: "Time",
                6: "Date Time",
                7: "URL",
                8: "Email",
                9: "Textarea",
                10: "Select",
                11: "IP Address",
            },
            1: "Object",
            2: "User",
            3: "Confluence",
            4: "Group",
            5: "Version",
            6: "Project",
            7: "Status",
        }

        attribute_type_id = object_type_attribute_json["type"]
        default_type_id = object_type_attribute_json.get("defaultType", {}).get(
            "id", None
        )
        if attribute_type_id == 0:
            self.attribute_type = self.ATTRIBUTE_TYPES[0][default_type_id]
        else:
            self.attribute_type = self.ATTRIBUTE_TYPES[attribute_type_id]

    def __str__(self):
        return f"InsightObjectTypeAttribute: {self.name}"


if __name__ == "__main__":
    # Poor man's debugging
    insight = Insight(os.environ["INSIGHT_URL"], None, webbrowser_auth=True)
    insight_object_schema = InsightObjectSchema(insight, 12)
    object_gen = insight_object_schema.search_iql(
        'objectType IN ("Desktop","Laptop","Tablet","Virtuelle Maschine") and Seriennummer = 052211303453dfgdfgdfg'
    )

    print([i for i in object_gen])
