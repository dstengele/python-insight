from lazy import lazy
from InsightObjectAttribute import InsightObjectAttribute


class InsightObject(object):
    def __init__(self, insight, object_schema, object_id):
        self.insight = insight
        self.id = object_id

    def __str__(self):
        return f"InsightObject: {self.name}"

    @lazy
    def object_schema(self):
        return self.insight.object_schemas[
            self.object_json["objectType"]["objectSchemaId"]
        ]

    @lazy
    def name(self):
        return self.object_json["label"]

    @lazy
    def object_json(self):
        return self.insight.do_api_request(f"/object/{self.id}")

    @lazy
    def attributes(self):
        attributes = {}

        for attribute_json in self.object_json["attributes"]:
            attribute_object = InsightObjectAttribute(
                self,
                attribute_json["objectTypeAttributeId"],
                attribute_json["objectAttributeValues"],
            )
            attributes[attribute_object.name] = attribute_object
        return attributes
