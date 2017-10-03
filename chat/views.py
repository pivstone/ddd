# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.http import HttpResponse

from ddd import settings


def receiver(request):
    settings.ES.index(index=settings.INDEX_NAME, doc_type=settings.INDEX_NAME, body=request.body)
    return HttpResponse()
