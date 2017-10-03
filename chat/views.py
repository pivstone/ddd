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
    data = dict(urllib.parse.parse_qsl(six.text_type(body)))
    LOG.info(data)
    settings.ES.index(index=settings.INDEX_NAME, doc_type=data["b'Event"], body=data)
    return HttpResponse()
