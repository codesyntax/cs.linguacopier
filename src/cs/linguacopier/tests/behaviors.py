"""Test-only behavior providing controlled (token) and structured fields."""

from collective.z3cform.datagridfield.datagridfield import DataGridFieldWidgetFactory
from collective.z3cform.datagridfield.row import DictRow
from plone.autoform import directives
from plone.autoform.interfaces import IFormFieldProvider
from z3c.relationfield.interfaces import IRelationList
from z3c.relationfield.schema import RelationChoice
from z3c.relationfield.schema import RelationList
from zope import schema
from zope.interface import alsoProvides
from zope.interface import implementer
from zope.interface import Interface


class ITestCategorized(Interface):
    """A behavior with vocabulary/taxonomy-style controlled fields."""

    test_category = schema.Choice(
        title="Test category",
        description="A token-valued field.",
        values=("alpha", "beta", "gamma"),
        required=False,
    )

    test_topics = schema.List(
        title="Test topics",
        description="A collection of token values.",
        value_type=schema.Choice(values=("one", "two", "three")),
        required=False,
    )


alsoProvides(ITestCategorized, IFormFieldProvider)


@implementer(ITestCategorized)
class TestCategorized:
    """Store the controlled-field values as attributes on the content."""

    def __init__(self, context):
        self.context = context

    @property
    def test_category(self):
        return getattr(self.context, "test_category", None)

    @test_category.setter
    def test_category(self, value):
        self.context.test_category = value

    @property
    def test_topics(self):
        return getattr(self.context, "test_topics", None)

    @test_topics.setter
    def test_topics(self, value):
        self.context.test_topics = value


class ITestSubRow(Interface):
    """A row schema for a data grid nested inside another one."""

    note = schema.TextLine(title="Note", required=False)


class ITestDataGridRow(Interface):
    """A row schema for a test data grid: text, non-text and a nested grid."""

    label = schema.TextLine(title="Label", required=False)
    amount = schema.Int(title="Amount", required=False)
    sub_rows = schema.List(
        title="Sub rows",
        value_type=DictRow(schema=ITestSubRow),
        required=False,
    )


class ITestDataGrid(Interface):
    """A behavior with a data grid field."""

    test_rows = schema.List(
        title="Rows",
        value_type=DictRow(schema=ITestDataGridRow),
        required=False,
    )


directives.widget("test_rows", DataGridFieldWidgetFactory)
alsoProvides(ITestDataGrid, IFormFieldProvider)


@implementer(ITestDataGrid)
class TestDataGrid:
    """Store the data grid value as an attribute on the content."""

    def __init__(self, context):
        self.context = context

    @property
    def test_rows(self):
        return getattr(self.context, "test_rows", None)

    @test_rows.setter
    def test_rows(self, value):
        self.context.test_rows = value


class ITestRelated(Interface):
    """A behavior with a relation list backed by a separate adapter.

    The adapter is not the content object, so it does not expose
    ``Language()``, which the relation remapping must not rely on.
    """

    test_related = RelationList(
        title="Test related",
        value_type=RelationChoice(vocabulary="plone.app.vocabularies.Catalog"),
        required=False,
    )


alsoProvides(ITestRelated, IFormFieldProvider)


@implementer(ITestRelated)
class TestRelated:
    """Store the relation list value as an attribute on the content."""

    def __init__(self, context):
        self.context = context

    @property
    def test_related(self):
        return getattr(self.context, "test_related", None)

    @test_related.setter
    def test_related(self, value):
        self.context.test_related = value


class ITestImageRelationList(IRelationList):
    """A project-specific relation list marker, as cs_dynamicpages defines."""


@implementer(ITestImageRelationList)
class ImageRelationList(RelationList):
    """A RelationList subclass carrying a project-specific marker.

    This mirrors cs_dynamicpages' ``ImageRelationList``.
    """


@implementer(IRelationList)
class InterfaceRelationList(schema.List):
    """A list field that provides IRelationList without subclassing it.

    Only an interface-based check recognises its values as relations.
    """


class ITestCustomRelated(Interface):
    """A behavior with project-specific relation list fields."""

    test_related_image = ImageRelationList(
        title="Related image",
        value_type=RelationChoice(vocabulary="plone.app.vocabularies.Catalog"),
        required=False,
    )

    test_interface_related = InterfaceRelationList(
        title="Interface relation",
        value_type=RelationChoice(vocabulary="plone.app.vocabularies.Catalog"),
        required=False,
    )


alsoProvides(ITestCustomRelated, IFormFieldProvider)


@implementer(ITestCustomRelated)
class TestCustomRelated:
    """Store both relation list values as attributes on the content."""

    def __init__(self, context):
        self.context = context

    @property
    def test_related_image(self):
        return getattr(self.context, "test_related_image", None)

    @test_related_image.setter
    def test_related_image(self, value):
        self.context.test_related_image = value

    @property
    def test_interface_related(self):
        return getattr(self.context, "test_interface_related", None)

    @test_interface_related.setter
    def test_interface_related(self, value):
        self.context.test_interface_related = value
