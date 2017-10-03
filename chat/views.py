# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

import urllib.parse
from django.http import HttpResponse
from django.utils import six

from ddd import settings

LOG = logging.getLogger(__name__)


def receiver(request):
    body = six.text_type(request.body)
    query_string = six.text_type(body)
    if query_string.startswith("b'"):
        query_string = query_string[2:]
    data = dict(urllib.parse.parse_qsl(query_string))
    LOG.info(data)
    if "Event" in data:
        del data['Event']
        settings.ES.index(index=settings.INDEX_NAME, doc_type=data["Event"], body=data)
    return HttpResponse()
