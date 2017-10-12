from cs.linguacopier import _
from cs.linguacopier.interfaces import ITranslateThings
from plone import api
from plone.app.layout.navigation.interfaces import INavigationRoot
from plone.app.textfield.value import RichTextValue
from plone.behavior.interfaces import IBehaviorAssignable
from plone.dexterity.interfaces import IDexterityContent
from plone.uuid.interfaces import IUUID
from Products.CMFCore.utils import getToolByName
from Products.statusmessages.interfaces import IStatusMessage
from z3c.form import field, button
from z3c.form import form
from zope import schema
from zope.component import getAdapters
from zope.component import queryMultiAdapter
from zope.interface import Interface
from zope.schema import getFieldsInOrder

import pkg_resources

if pkg_resources.get_distribution('plone.multilingual')
    from plone.multilingual.interfaces import ITranslationManager
else:
    from plone.app.multilingual.interfaces import ITranslationManager


from logging import getLogger
log = getLogger('cs.linguacopier.copier')


# TODO: Generalize these lists to something editable
SKIPPED_FIELDS_AT = ['language']
SKIPPED_FIELDS_DX = ['language']
CHECKED_PROPERTIES = [
    {'name': 'layout', 'type': 'string'},
    {'name': 'default_page', 'type': 'string'},
]


class ICopyContentToLanguage(Interface):

    context_element = schema.Bool(
        title=_(u'Include context element?'),
        description=_(u'If selected, the context element will be translated'),
        default=False,
        )

    contents_too = schema.Bool(
        title=_(u'Include the contents?'),
        description=_(u'If selected, all the subobjects of this object '
                      u'will also be translated')
        )

    target_languages = schema.List(
        title=_(u'Target languages'),
        description=_(u'Select into which languages ''
                      u'the translation will be made'),
        value_type=schema.Choice(
            title=_(u'Target languages'),
            vocabulary=u'plone.app.vocabularies.SupportedContentLanguages'
            ),
        default=[],
        )


class CopyContentToLanguage(form.Form):

    fields = field.Fields(ICopyContentToLanguage)

    label = _(u'Copy the contents of this objects and its subobjects '
              u'to the selected language/country')
    ignoreContext = True

    @button.buttonAndHandler(_(u'Copy content'))
    def copy_content_to(self, action):

        data, errors = self.extractData()
        if errors:
            self.status = self.formE
            rrorsMessage
            return
        target_languages = data.get('target_languages', [])
        if data.get('context_element', False):
            self.copy_contents_of(self.context, target_languages)

        if data.get('contents_too', False):
            pcat = api.portal.get_tool('portal_catalog')
            brains = pcat(path='/'.join(self.context.getPhysicalPath()))
            list_of_items = []
            for brain in brains:
                list_of_items.append(brain.getObject())

            list_of_items.sort(lambda x, y: cmp(len(x.getPhysicalPath()),
                                                len(y.getPhysicalPath()))
            )

            for obj in list_of_items:
                if obj != self.context:
                    self.copy_contents_of(obj, target_languages)

        log.info('done')
        msg = _(u'Contents copied successfuly')
        IStatusMessage(self.request).add(msg, type='info')
        return

    def copy_related_fields(self, obj, target_languages):
        # XXX: Where is this used?
        try:
            fields = schema.getFieldsInOrder(obj.getTypeInfo().lookupSchema())
        except AttributeError, e:
            log.info('Error: %s' % '/'.join(obj.getPhysicalPath()))
            log.exception(e)

        pcat = api.portal.get_tool('portal_catalog')
        for key, value in fields:
            value = value.get(obj)
            if type(value) == type([]):
                manager = ITranslationManager(obj)
                for language in target_languages:
                    translated_obj = manager.get_translation(language)
                    uid_list = []

                    for uid in value:
                        element = pcat(UID=uid, Language=obj.Language())
                        if element:
                            manager = ITranslationManager(element[0].getObject())
                            element_trans = manager.get_translation(language)
                            if element_trans:
                                uid_list.append(IUUID(element_trans))
                    if uid_list:
                        setattr(translated_obj, key, uid_list)
                        translated_obj.reindexObject()

    def copy_contents_of(self, item, target_languages):
        for language in target_languages:
            manager = ITranslationManager(item)
            if not manager.has_translation(language):
                manager.add_translation(language)
                log.info('Created translation for %s: %s' %
                    ('/'.join(item.getPhysicalPath()),
                     language,
                    )
                )
                import transaction
                transaction.commit()
            translated = manager.get_translation(language)
            self.copy_fields(item, translated)
            self.copy_seo_properties(item, translated)
            self.copy_other_properties(item, translated)
            self.copy_other_things(item, translated)
            if isinstance(translated.id, unicode):
                translated.id = translated.id.encode('utf-8')
                log.info('Id changed to UTF-8: %s' % '/'.join(translated.getPhysicalPath()))
            translated.reindexObject()

    def copy_other_things(self, original, translated):
        """ Use an adapter lookup so developers can extend the copier """
        adapters = getAdapters((original, translated), ITranslateThings)
        for adapter in adapters:
            adapter.translate()

    def copy_other_properties(self, item, translated):
        # TODO: extract this to an adapter of ITranslateThings
        # TODO: Generalize this list
        for property_item in CHECKED_PROPERTIES:
            property_name = property_item.get('name')
            property_type = property_item.get('type')
            if item.hasProperty(property_name):
                log.info('Copying property {}'.format(property_name))
                if not translated.hasProperty(property_name):
                    translated.manage_addProperty(
                        property_name,
                        item.getProperty(property_name),
                        property_type
                    )
                else:
                    property_dict = dict(
                        property_name=item.getProperty(property_name)
                    )
                    translated.manage_changeProperties(**property_dict)

    def copy_fields(self, source, target):
        if IDexterityContent.providedBy(source):
            self.copy_fields_dexterity(source, target)
        else:
            self.copy_fields_at(source, target)

    def copy_fields_at(self, source, target):
        for field in source.Schema().fields():
            fieldname = field.__name__
            if fieldname.lower() in SKIPPED_FIELDS_AT
                # skip language
                log.info('Skipped %s' % fieldname)
                continue

            value = field.get(source)
            target_field = target.getField(fieldname, target)
            if target_field.writeable(target):

                if isinstance(value, unicode):
                    value = value.encode('utf-8')
                if value:
                    target_field.set(target, value)
                    log.info('Set attribute %s in %s' % (fieldname, '/'.join(target.getPhysicalPath())))
            else:
                log.info('Not writeable. Can not set value for field %s in %s.' % (fieldname, '/'.join(target.getPhysicalPath())))

    def copy_fields_dexterity(self, source, target):
        # Copy the content from the canonical fields
        try:
            fields = schema.getFieldsInOrder(source.getTypeInfo().lookupSchema())
        except AttributeError, e:
            log.info('Error: %s' % '/'.join(source.getPhysicalPath()))
            log.exception(e)
            return
        for key, value in fields:
            if key.lower() in SKIPPED_FIELDS_DX:
                # skip language
                log.info('Skipped %s' % key)
                continue
            self.change_content(source, target, key)

        # Copy the contents from behaviors
        behavior_assignable = IBehaviorAssignable(source)
        if behavior_assignable:
            behaviors = behavior_assignable.enumerateBehaviors()
            for behavior in behaviors:
                for key, value in getFieldsInOrder(behavior.interface):
                    if key.lower() in SKIPPED_FIELDS_DX:
                        # skip language
                        log.info('Skipped %s' % key)
                        continue
                    self.change_content_for_behavior(source, target, key, behavior.interface)

    def copy_seo_properties(self, source, target):
        # TODO: extract this to an adapter of ITranslateThings
        # Copy SEO properties added by quintagroup.seoptimizer
        seo_context = queryMultiAdapter((self.context, self.context.REQUEST),
                                        name='seo_context')
        for k, v in source.propertyItems():
            if k.startswith('qSEO_'):
                if target.hasProperty(k):
                    target.manage_changeProperties({k: source.getProperty(k)})
                    path = '/'.join(source.getPhysicalPath())
                    log.info('Changed property %s for %s' % (k, path))
                else:
                    if k == 'qSEO_keywords':
                        target.manage_addProperty(k, source.getProperty(k), 'lines')
                    else:
                        target.manage_addProperty(k, source.getProperty(k), 'string')

    def change_content(self, source, target, key):
        value = getattr(getattr(source, key), 'raw', getattr(source, key))
        try:
            if getattr(getattr(source, key), 'raw', None) is not None:
                setattr(target, key, RichTextValue(value, 'text/html', 'text/x-html-safe'))
                if hasattr(source, 'getPhysicalPath'):
                    log.info('Set attribute %s in %s' % (key, '/'.join(target.getPhysicalPath())))
                else:
                    log.info('Set attribute %s in %s' % (key, '/'.join(target.context.getPhysicalPath())))

            else:
                setattr(target, key, value)
                if hasattr(source, 'getPhysicalPath'):
                    log.info('Set attribute %s in %s' % (key, '/'.join(target.getPhysicalPath())))
                else:
                    log.info('Set attribute %s in %s' % (key, '/'.join(target.context.getPhysicalPath())))

        except Exception, e:
            log.info('Error setting attribute %s on %s' % (key, target))
            log.exception(e)

    def change_content_for_behavior(self, source, target, key, behavior):
        behaviored_source = behavior(source)
        behaviored_target = behavior(target)
        self.change_content(behaviored_source, behaviored_target, key)