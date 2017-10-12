# -*- coding: utf-8 -*-
"""Module where all interfaces, events and exceptions live."""

from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class ICsLinguacopierLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class ITranslateThings(Interface):
    """ This is a multi adapter on (original_item, translated_item)
        to be able to extend the copier with additional features when
        translating."""

    def translate():
        """ Method that does something with the original_item and the
            translated_item, probably translating special content-types,
            attributes, annotations, ..."""
