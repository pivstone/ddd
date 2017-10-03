# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

from django.http import HttpResponse

from ddd import settings

LOG = logging.getLogger(__name__)


def receiver(request):
    print ("==="+request.body)
    settings.ES.index(index=settings.INDEX_NAME, doc_type=settings.INDEX_NAME, body=request.body)
    return HttpResponse()
