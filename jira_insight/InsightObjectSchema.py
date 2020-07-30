import logging

from lazy import lazy

from .InsightObject import InsightObject
from .InsightObjectType import InsightObjectType
from .InsightObjectTypeAttribute import InsightObjectTypeAttribute


class InsightObjectSchema(object):
    def __init__(self, insight, insight_id):
        self.insight = insight
        self.id = insight_id
        object_schema_json = insight.do_api_request(f"/objectschema/{insight_id}")
        self.name = object_schema_json.get("name", None)
        self.key = object_schema_json.get("objectSchemaKey", None)
        self.description = object_schema_json.get("description", None)

    @lazy
    def object_types(self):
        object_types_json = self.insight.do_api_request(
            f"/objectschema/{self.id}/objecttypes/flat"
        )
        object_types = {}
        for object_type in object_types_json:
            object_types[object_type["id"]] = InsightObjectType(
                self.insight, object_type["id"]
            )
        return object_types

    @lazy
    def object_type_attributes(self):
        object_type_attributes_json = self.insight.do_api_request(
            f"/objectschema/{self.id}/attributes"
        )
        object_type_attributes = {}
        for object_type_attribute_json in object_type_attributes_json:
            self.object_type_attributes[
                object_type_attribute_json["id"]
            ] = InsightObjectTypeAttribute(self, object_type_attribute_json)
        return object_type_attributes

    def __str__(self):
        return f"InsightObjectSchema: {self.name} ({self.key})"

    def search_iql(self, iql=None):
        api_path = "/iql/objects"
        params = {"objectSchemaId": self.id, "resultPerPage": 500}
        if iql is not None:
            params["iql"] = iql
        search_request = self.insight.do_api_request(api_path, params=params)
        search_results = search_request
        objects_json: list = search_results["objectEntries"]
        if not objects_json:
            return []

        # Get additional pages if neccessary
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
            object_to_add = InsightObject(self.insight, self, json_object["id"])
            objects_result.append(object_to_add)

        return objects_result

    def object_exists(self, object_id):
        return (
            self.insight.do_api_request(f"/object/{object_id}", "head").status_code
            == 200
        )
