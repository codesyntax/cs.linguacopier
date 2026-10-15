"""Test-only behavior providing controlled (token) and structured fields."""

from collective.z3cform.datagridfield.datagridfield import DataGridFieldWidgetFactory
from collective.z3cform.datagridfield.row import DictRow
from plone.autoform import directives
from plone.autoform.interfaces import IFormFieldProvider
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
