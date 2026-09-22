"""Every model on this service's Base must inherit an audit mixin, or be in _EXEMPT."""

import app.models
from app.models.base import Base
from shared.tests.audit_mixin_coverage import assert_full_audit_mixin_coverage

_EXEMPT: dict[str, str] = {
    "SessionModel": "system-issued auth session tied 1:1 to user_id, not a user-edited resource",
}


def test_every_model_inherits_audit_mixin():
    assert_full_audit_mixin_coverage(app.models, Base, _EXEMPT)
