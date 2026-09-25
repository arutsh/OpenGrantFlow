import factory
from uuid import uuid4

from app.models.export_template import ExportTemplateModel
from app.schemas.export_template_schema import ExportTemplateOptions, TemplateVisibility


class ExportTemplateFactory(factory.Factory):
    class Meta:
        model = ExportTemplateModel

    id = factory.LazyFunction(uuid4)
    owner_customer_id = factory.LazyFunction(uuid4)
    is_system_default = factory.LazyAttribute(lambda o: o.owner_customer_id is None)
    name = factory.Faker("word")
    visibility = TemplateVisibility.private
    options = factory.LazyFunction(lambda: ExportTemplateOptions().model_dump(mode="json"))
    version = 1
