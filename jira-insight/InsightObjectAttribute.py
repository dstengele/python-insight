from lazy import lazy
import datetime

from InsightObject import InsightObject


class InsightObjectAttribute(object):
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
                        self.insight_object.object_schema,
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
