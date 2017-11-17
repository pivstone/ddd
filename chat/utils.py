# coding=utf-8
from __future__ import unicode_literals


class Node(dict):
    def __init__(self, **kwargs):
        super(Node, self).__init__(**kwargs)
        self.end = []
        self.root_flag = False


class DFA(object):
    def __init__(self):
        self.root = Node()
        self.root.root_flag = True

    def add(self, key, value):
        key = key.lower()
        node = self.root
        i = 0
        while i < len(key):
            term = key[i]
            i += 1
            if term not in node:
                node.update({term: Node()})
            node = node[term]
        if not node.end:
            node.end = [value]
        node.end.append(value)

    def search(self, key):
        node = self.root
        i = 0
        while i < len(key):
            term = key[i]
            i += 1
            if term in node:
                node = node[term]
                if node.end:
                    yield node.end
                    node = self.root
            else:
                yield None
        yield None

    def __getitem__(self, item):
        node = self.root
        for term in item:
            if term in node:
                node = node[term]
            elif node.end:
                break
            else:
                return []
        return node.end

    def __str__(self):
        return self.root.__str__()


if __name__ == '__main__':
    d = DFA()
    d.add("绑定", "abc")
    print(d["绑定"])


class PMContext():
    data = dict()

    def __init__(self, text):
        import re
        data = ""
        for temp in text.split("\n"):
            if re.match(r"^=+.+=+$", temp):
                continue
            if re.match(r"^<+.+>$", temp):
                continue
            if temp.startswith("&lt;"):
                continue
            data += temp
        text = data
        temp_group = text.split("}}")
        for temp in temp_group:
            group_list = temp.split("|")
            group_name = group_list[0]
            group_name = group_name.replace("{{", "").replace("=", "").replace(" ", "")
            temp_dict = dict()
            for temp_data in group_list[1:]:
                if re.match(r"^[^=]+=[^=]+$", temp_data):
                    temp_pair = temp_data.split("=")
                    temp_dict[temp_pair[0]] = temp_pair[1]
            self.data[group_name] = temp_dict
