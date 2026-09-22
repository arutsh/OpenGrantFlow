import importlib
import pkgutil
from types import ModuleType

from shared.db.audit_mixin import AuditColumnsMixin


def assert_full_audit_mixin_coverage(
    models_package: ModuleType, base, exempt: dict[str, str]
) -> None:
    """Imports every module under models_package so a missing __init__.py import can't hide it."""
    prefix = models_package.__name__ + "."
    for module_info in pkgutil.iter_modules(models_package.__path__, prefix):
        importlib.import_module(module_info.name)

    missing = sorted(
        mapper.class_.__name__
        for mapper in base.registry.mappers
        if not issubclass(mapper.class_, AuditColumnsMixin) and mapper.class_.__name__ not in exempt
    )
    assert not missing, f"Models missing AuditMixin/AuditColumnsMixin: {missing}"
