The copier now chooses automatically whether to run a copy directly or in the
background. A copy with nothing to translate runs directly; a translated copy
runs directly when the estimated work (objects times target languages) fits the
configured limit and in the background otherwise. An explicit ``mode`` on the
request (``auto``, ``direct`` or ``background``) overrides the choice.