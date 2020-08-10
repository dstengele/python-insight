import datetime

import requests
from lazy import lazy
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import logging


class Insight:
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

        api_path = "/objectschema/list"
        object_schemas_json_request = self.do_api_request(api_path)
        object_schemas_json = object_schemas_json_request.get("objectschemas", {})
        self.object_schemas = {}
        logging.info("Loading object schemas")
        object_schemas_count = len(object_schemas_json)
        index = 1
        for object_schema_json in object_schemas_json:
            logging.info(
                f'Loading object schema {object_schema_json["name"]} ({index}/{object_schemas_count})'
            )
            object_schema_id = object_schema_json["id"]
            self.object_schemas[object_schema_id] = InsightObjectSchema(
                self, object_schema_id
            )
            index += 1

    def __str__(self):
        return f"Insight: {self.jira_url}"

    def do_api_request(self, path, method="get", json=None, params=None):
        if method == "get":
            request = self.retry_session.get(self.insight_api_url + path, params=params)
            request.raise_for_status()
            return request.json()
        if method == "post":
            request = self.retry_session.post(
                self.insight_api_url + path, json=json, params=params
            )
            request.raise_for_status()
            return request.json()
        if method == "head":
            request = self.retry_session.head(
                self.insight_api_url + path, params=params
            )
            request.raise_for_status()
            return request.json()
        raise NotImplementedError


class InsightObject:
    def __init__(self, insight, object_id, object_json=None):
        self.insight = insight
        self.id = object_id
        self.object_json = object_json
        if not self.object_json:
            self.object_json = self.insight.do_api_request(f"/object/{self.id}")
        self.name = self.object_json["label"]
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

    def __str__(self):
        return f"InsightObject: {self.name}"


class InsightObjectAttribute:
    def __init__(self, insight_object, attribute_id, values_json=None):
        self.insight_object = insight_object
        self.id = attribute_id
        self.object_type_attribute = self.insight_object.object_schema.object_type_attributes[
            self.id
        ]
        self.name = self.object_type_attribute.name
        self.values_json = values_json

    @lazy
    def value(self):
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
            if self.object_type_attribute.attribute_type == "Date":
                return datetime.datetime.strptime(
                    value_json.get("value", None), "%d.%m.%Y"
                ).date()
            if self.object_type_attribute.attribute_type == "Date Time":
                return datetime.datetime.strptime(
                    value_json.get("value", None), "%d.%m.%Y %H:%M"
                )

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

        object_types_json = self.insight.do_api_request(
            f"/objectschema/{self.id}/objecttypes/flat"
        )
        self.object_types = {}
        for object_type in object_types_json:
            self.object_types[object_type["id"]] = InsightObjectType(
                self.insight, object_type["id"], object_type
            )

        object_type_attributes_json = self.insight.do_api_request(
            f"/objectschema/{self.id}/attributes"
        )
        self.object_type_attributes = {}
        for object_type_attribute_json in object_type_attributes_json:
            self.object_type_attributes[
                object_type_attribute_json["id"]
            ] = InsightObjectTypeAttribute(self, object_type_attribute_json)

    def __str__(self):
        return f"InsightObjectSchema: {self.name} ({self.key})"

    def search_iql(self, iql=None):
        api_path = "/iql/objects"
        params = {"objectSchemaId": self.id, "resultPerPage": 500, "includeTypeAttributes": "true"}
        if iql is not None:
            params["iql"] = iql
        search_request = self.insight.do_api_request(api_path, params=params)
        search_results = search_request
        objects_json: list = search_results["objectEntries"]
        if not objects_json:
            return []

        # Get additional pages if necessary
        if search_results["pageSize"] > 1:
            for page_number in range(2, search_results["pageSize"] + 1):
                params["page"] = page_number
                logging.info(
                    f'Reading page {page_number} of {search_results["pageSize"]}'
                )
                page = self.insight.do_api_request(api_path, params=params)
                objects_json += page["objectEntries"]

        objects_result = []
        for json_object in objects_json:
            object_to_add = InsightObject(self.insight, json_object["id"], json_object)
            objects_result.append(object_to_add)

        return objects_result

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
