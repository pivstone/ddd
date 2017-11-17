# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import inspect
import logging

from django.core.cache import cache
from django.http import HttpResponse, Http404
from django.utils.encoding import python_2_unicode_compatible

from chat import handlers
from chat.handlers import AbstractHandler
from chat.utils import DFA
from ddd import settings

LOG = logging.getLogger(__name__)

class_members = inspect.getmembers(handlers, inspect.isclass)
router = DFA()


@python_2_unicode_compatible
class Session(object):
    CLUSTER = 2  # 群聊模式
    SINGLE = 1  # 一对一通话模式

    def __init__(self, data):
        if data['Event'] in ("TempSessionIM", "NormalIM",):
            self.sender = data["Sender"]
            self.type = self.SINGLE
        else:
            self.sender = data["GroupId"]
            self.type = self.CLUSTER
        self.data = dict()
        self.messages = list()

    def add_message(self, message):
        self.messages.append(message)
        if len(self.messages) > 50:
            self.messages = self.messages[-40:]

    def get_last_message(self):
        if self.messages:
            return self.messages[-1]
        return None

    def __str__(self):
        return "%s:%s" % (self.sender, self.type)

    def save(self):
        if hasattr(self, 'context'):
            cache.set("Veda:session:%s" % self.__str__(), self, 60 * 30)

    def clear(self):
        if hasattr(self, 'context'):
            cache.delete("Veda:session:%s" % self.__str__())
            cache.delete("Veda:session:handle:%s" % self.__str__())


class ContextManger(object):
    def register_handler(self, session, callback):
        handler_list = cache.get("Veda:session:handle:%s" % session.__str__())
        if handler_list:
            handler_list.insert(0, callback)
        cache.set("Veda:session:handle:%s" % session.__str__(), [callback], 60 * 10)

    def get_handler(self, session):
        return cache.get("Veda:session:handle:%s" % session.__str__())

    def cancel_handler(self, session, index):
        handler_list = cache.get("Veda:session:handle:%s" % session.__str__())
        if handler_list:
            del handler_list[index]
        if not handler_list:
            cache.delete("Veda:session:handle:%s" % session.__str__())
        else:
            cache.set("Veda:session:handle:%s" % session.__str__(), handler_list, 60 * 10)


for clz in class_members:
    if issubclass(clz[1], AbstractHandler) and clz[1] != AbstractHandler:
        handler = clz[1]()
        logging.info("router register command:%s ,clz:%s" % (handler.get_cmd(), handler.__class__()))
        router.add(handler.get_cmd(), handler)
context = ContextManger()


def watch(request):
    data = request.POST
    LOG.info(data)
    if "Event" in data:
        doc_type = data.pop('Event')
        settings.ES.index(index=settings.INDEX_NAME, doc_type=doc_type, body=data)
    if data['Event'] in ("ClusterIM", "TempSessionIM", "NormalIM",):
        # 处理消息
        message = data['Message']
        # 处理Session
        session = Session(data)
        temp_session = cache.get("Veda:session:%s" % session.__str__())
        if temp_session and isinstance(temp_session, Session):
            session = temp_session
        # 插入最新消息
        session.add_message(data)
        # 保存session
        setattr(session, 'context', context)  # 注入上下文切换器
        session.save()
        bind = False
        # 优先重现上下文
        pre_handler = context.get_handler(session)
        if pre_handler:
            for index, handle in enumerate(pre_handler):
                result = handle.pre_handle(data=data, session=session)
                if result:
                    context.cancel_handler(session, index)
                    return HttpResponse(result)
        # 消息分发
        for handle in router[message]:
            if handle.bind():
                if not bind:
                    raise Http404()
            if handle.super_cmd():
                qq = data['Sender']
                if qq != "371634316":
                    raise Http404()
            if not handle.group():
                if data['Event'] not in ("TempSessionIM", "NormalIM",):
                    raise Http404()
            result = handle.pre_handle(data=data, session=session)
            if result:
                return HttpResponse(result)
    return HttpResponse(status=404)
