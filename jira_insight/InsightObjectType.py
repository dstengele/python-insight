import logging

from .InsightObjectSchema import InsightObjectSchema
from .InsightObject import InsightObject


class InsightObjectType(object):
    def __init__(self, insight, insight_id):
        self.insight = insight
        self.id = insight_id
        logging.info(f"Loading Insight object type with ID {insight_id}")
        object_type_json = self.insight.do_api_request(f"/objecttype/{insight_id}")
        self.name = object_type_json.get("name", None)
        self.description = object_type_json.get("description", None)
        self.object_schema_id = object_type_json.get("objectSchemaId", None)

    def __str__(self):
        return f"InsightObjectType: {self.name}"

    def create_object(self, name, attributes: dict):
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
        object_schema = InsightObjectSchema(self.insight, self.object_schema_id)
        created_object = InsightObject(self.insight, object_schema, object_id)
        return created_object
