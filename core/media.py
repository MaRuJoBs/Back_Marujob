"""Development media serving must not bypass chat participant permissions."""

import posixpath

from django.http import Http404
from django.views.static import serve


def public_media(request, path, document_root=None, **kwargs):
    normalized = posixpath.normpath(path.replace('\\', '/')).lstrip('/')
    if normalized.split('/')[0] == 'chat_files':
        raise Http404
    return serve(request, normalized, document_root=document_root, **kwargs)
