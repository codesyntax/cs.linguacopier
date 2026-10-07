"""Test-only behavior providing controlled (token) fields."""

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
