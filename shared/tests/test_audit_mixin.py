import uuid

import pytest
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from shared.db.audit_mixin import AuditColumnsMixin, AuditMixin
from shared.security.current_user_context import reset_current_user_id, set_current_user_id


class _Base(DeclarativeBase):
    pass


class _WidgetModel(_Base, AuditMixin):
    """Throwaway model exercising id-bearing AuditMixin."""

    __tablename__ = "widgets"

    name: Mapped[str] = mapped_column(default="widget")
    gadgets: Mapped[list["_GadgetModel"]] = relationship(back_populates="widget")


class _GadgetModel(_Base):
    """Throwaway related model whose FK lives on its own table, not the widget's."""

    __tablename__ = "gadgets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    widget_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("widgets.id"))
    widget: Mapped["_WidgetModel"] = relationship(back_populates="gadgets")


class _TagModel(_Base, AuditColumnsMixin):
    """Throwaway model exercising PK-less AuditColumnsMixin with a custom PK."""

    __tablename__ = "tags"

    slug: Mapped[str] = mapped_column(primary_key=True)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    _Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class TestAuditMixinListener:
    def test_created_by_set_and_updated_by_stays_null_on_insert_when_context_set(self, session):
        user_id = uuid.uuid4()
        token = set_current_user_id(user_id)
        try:
            widget = _WidgetModel()
            session.add(widget)
            session.commit()
        finally:
            reset_current_user_id(token)

        assert widget.created_by == user_id
        assert widget.updated_by is None

    def test_created_by_stays_null_when_context_unset(self, session):
        widget = _WidgetModel()
        session.add(widget)
        session.commit()

        assert widget.created_by is None
        assert widget.updated_by is None

    def test_updated_by_changes_to_new_user_on_update(self, session):
        creator_id = uuid.uuid4()
        token = set_current_user_id(creator_id)
        try:
            widget = _WidgetModel()
            session.add(widget)
            session.commit()
        finally:
            reset_current_user_id(token)

        updater_id = uuid.uuid4()
        token = set_current_user_id(updater_id)
        try:
            widget.name = "renamed"
            session.commit()
        finally:
            reset_current_user_id(token)

        assert widget.created_by == creator_id
        assert widget.updated_by == updater_id

    def test_updated_by_stays_null_on_update_when_context_unset(self, session):
        widget = _WidgetModel()
        session.add(widget)
        session.commit()

        widget.name = "renamed"
        session.commit()

        assert widget.updated_by is None

    def test_manually_set_created_by_is_not_clobbered_when_context_unset(self, session):
        manual_user_id = uuid.uuid4()
        widget = _WidgetModel(created_by=manual_user_id, updated_by=manual_user_id)
        session.add(widget)
        session.commit()

        assert widget.created_by == manual_user_id
        assert widget.updated_by == manual_user_id

    def test_manually_set_updated_by_is_not_clobbered_when_context_unset(self, session):
        widget = _WidgetModel()
        session.add(widget)
        session.commit()

        manual_user_id = uuid.uuid4()
        widget.name = "renamed"
        widget.updated_by = manual_user_id
        session.commit()

        assert widget.updated_by == manual_user_id

    def test_relationship_only_mutation_does_not_update_updated_by(self, session):
        creator_id = uuid.uuid4()
        token = set_current_user_id(creator_id)
        try:
            widget = _WidgetModel()
            session.add(widget)
            session.commit()
        finally:
            reset_current_user_id(token)

        other_user_id = uuid.uuid4()
        token = set_current_user_id(other_user_id)
        try:
            gadget = _GadgetModel()
            session.add(gadget)
            widget.gadgets.append(gadget)
            session.commit()
        finally:
            reset_current_user_id(token)

        assert widget.updated_by is None


class TestAuditColumnsMixinListener:
    def test_created_by_set_and_updated_by_stays_null_on_insert_when_context_set(self, session):
        user_id = uuid.uuid4()
        token = set_current_user_id(user_id)
        try:
            tag = _TagModel(slug="acme")
            session.add(tag)
            session.commit()
        finally:
            reset_current_user_id(token)

        assert tag.created_by == user_id
        assert tag.updated_by is None

    def test_created_by_stays_null_when_context_unset(self, session):
        tag = _TagModel(slug="acme")
        session.add(tag)
        session.commit()

        assert tag.created_by is None
        assert tag.updated_by is None
