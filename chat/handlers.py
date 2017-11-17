# coding=utf-8
from __future__ import unicode_literals

import json
import logging
import random
import re

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.mail import send_mail
from six import python_2_unicode_compatible

logger = logging.getLogger(__name__)


class AbstractHandler(object):
    def __init__(self):
        self.session = None

    def get_cmd(self):
        raise NotImplementedError()

    def pre_handle(self, data, session):
        self.session = session
        result = self.handle(data)
        self.session.save()
        return result

    def handle(self, data):
        raise NotImplementedError()

    def bind(self):
        """
        是否需要绑定
        :return:
        """
        return False

    def super_cmd(self):
        """
        是否为超级命令
        :return:
        """
        return False

    def group(self):
        """
        是否允许在群中使用
        :return:
        """
        return True


@python_2_unicode_compatible
class AbstractStateHandler(object):
    def __init__(self):
        self.session = None

    # 具有状态的Handler
    def pre_handle(self, data, session):
        self.session = session
        result = self.handle(data)
        self.session.save()
        return result

    def handle(self, data):
        raise NotImplementedError()

    def __str__(self):
        return self.__name__


message_type_mapping = {
    "NormalIM": 0,
    "TempSessionIM": 1,
    "ClusterIM": 2,
    "DiscussionIM": 3,
}


class CardFindHandler(AbstractHandler):
    def get_cmd(self):
        return "card"

    def handle(self, data):
        message = data["Message"]
        if len(message.split()) < 2:
            return "命令格式不对"
        name = message.split()[1]
        r = requests.get("http://www.ourocg.cn/S.aspx", {"key": name})
        soup = BeautifulSoup(r.content)
        card_url = soup.find('a', href=re.compile(r"Cards/View"))
        data = ""
        if not card_url:
            data += "你要找的是不是\n"
            for suggest in soup.find('a', href=re.compile(r"^/S")):
                data += "  %s" % suggest
            return data
        r = requests.get("http://www.ourocg.cn%s" % card_url['href'])
        if r.status_code != 200:
            print("%s找不到啊" % name)
        soup = BeautifulSoup(r.content)
        i = 1
        for attr in soup.find("div", attrs={"class": "card row"}):
            try:
                if i == 1:
                    i += 1
                    continue
                if hasattr(attr, "text") and attr.text:
                    data += attr.text
                    i += 1
                else:
                    continue
                if i % 2 == 0:
                    data += "\n"
                else:
                    data += ":"
            except AttributeError:
                i -= 1
                pass
        data = data.split("收录详情")[0]
        image_url = soup.find("div", attrs={"class": "img"}).img.get("src")
        return "[Image]%s[/Image]" % image_url + data


class WowHandler(AbstractHandler):
    tag = "var items_data="

    def get_cmd(self):
        return "wow"

    def handle(self, data):
        message = data["Message"]
        if len(message.split()) < 2:
            return "命令格式不对"
        name = message.split()[1]
        if not re.match(r"^\d+$", name):
            r = requests.get("http://db.178.com/wow/cn/search.html", params={"name": name, "wtf": 1})
            soup = BeautifulSoup(r.content)
            data = None
            for s in soup.findAll('script', src=None):
                if self.tag in s.text:
                    temp = s.text.split(";")
                    for t in temp:
                        if self.tag in t:
                            data = json.loads(t.replace(self.tag, ""))
            if not data:
                return "%s相关物品没有找到诶( ；´Д｀)" % name
            result = "物品列表：\n"
            for d in data:
                result += "ID：%s,名字：%s，物品等级：%s,需要等级：%s，类型：%s\n" % (d[0], d[1], d[6], d[7], d[12])
            result += "查看详情，wow [物品ID]"
            return result
        else:
            r = requests.get("http://db.178.com/wow/cn/item/%s.html" % name)
            if r.status_code == 404:
                return "ID:%s没有找到诶( ；´Д｀)" % name
            soup = BeautifulSoup(r.text)
            data = soup.find("div", id="bbcode_content").__str__()
            data = re.sub(r"\s", "", data)
            data = re.sub(r"\[img\]", "{img}", data)
            data = re.sub(r"\[/img\]", "{/img}", data)
            data = re.sub(r"\<[^\<]+\>", "\n", data)
            data = re.sub(r"\[[^\[]+\]", "", data)
            data = data.replace("{img}", "[Image]")
            data = data.replace("{/img}", "[/Image]")
            return data


class PokemonFindHandler(AbstractHandler):
    param_list = (
        "HP", "攻击", "防御", "特攻", "特防", "速度", 'enname', 'type', 'name', 'jname', 'enname', 'ability2', 'ability1',
        'abilityd', 'type', 'ndex')
    template = """
    [Image]{cover}[/Image]\nNo:{ndex:<8}\n名字:{name:<8}\n日文:{jname:<8}\n英文:{enname:<8}\n----------------------------------------\n属性:{type:<8}\n特性:{ability1:<8}特性:{ability2:<8}其他:{abilityd:<8}\n----------------------------------------\n种族值:\nHP  :{HP:<8}攻击:{攻击:<8}防御:{防御:<8}\n特攻:{特攻:<8}特防:{特防:<8}速度:{速度:<8}
    """

    def get_cmd(self):
        return "pm"

    def handle(self, data, user=None):
        message = data[u"Message"]
        if len(message.split()) < 2:
            return u"命令格式不对"
        name = message.split()[1]
        r = requests.get("http://wiki.52poke.com/index.php", {"search": name, "go": u"前往"})
        soup = BeautifulSoup(r.text, 'html.parser')
        if not soup.find("a", attrs={"class": "image"}):
            return "找不到"
        cover = "http:" + soup.find("a", attrs={"class": "image"}).img.get('data-url')
        href = soup.find("li", id="ca-viewsource").find("a")['href']
        r = requests.get("http://wiki.52poke.com%s" % href)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.find("textarea").text
        import mwparserfromhell
        wiki = mwparserfromhell.parse(text)
        data = {}
        for meta in wiki.filter_templates(recursive=False):
            for param in self.param_list:
                if meta.has(param) and param not in data:
                    data.update({param: meta.get(param).value})
        for param in self.param_list:
            if param not in data:
                data.update({param: "无"})
        data.update({'cover': cover})
        print(data)
        return self.template.format(**data)


class RollHandler(AbstractHandler):
    def get_cmd(self):
        return "roll"

    def handle(self, data):
        message = data["Message"]
        num = 100
        if len(message.split()) > 1:
            num_text = message.split()[1]
            if not re.match(r"^\d+$", num_text):
                return "命令格式不对"
            num = int(num_text)
        return "命运的骰子数:%s" % random.randint(0, num)


class CoinHandler(AbstractHandler):
    def get_cmd(self):
        return "硬币"

    def handle(self, data):
        return "命运的硬币:%s面" % random.choice("正反")


class RepeatHandler(AbstractStateHandler):
    """
    重复上一个命令
    """

    def handle(self, data):
        data = self.session.get_last_message()
        if 'Message' in data:
            return data['Message']
        else:
            return "木有找到上一个命令哦"


class DebugHandler(AbstractStateHandler):
    def __init__(self, count=10):
        super(DebugHandler, self).__init__()
        if count > 100:
            count = 10
        self.count = count

    def handle(self, data):
        record_count = self.session.data.get('record_count', 0)
        if int(record_count) > self.count:
            debug_code = self.session.data.get('record_code', "(null)")
            msg = ""
            chat = []
            for data in self.session.messages[-record_count:]:
                msg += "\n" + json.dumps(data, ensure_ascii=False)
                chat.append(data['Message'])
            settings.BOT.train(chat)
            msg += "\nSession Data:%s" % json.dumps(self.session.data, ensure_ascii=False)
            if hasattr(self.session, 'user'):
                msg += "\nSession User-ID:%s" % self.session.user.id
            send_mail(subject=u"[Veda-DEBUG-%s]" % debug_code, message=msg,
                      from_email="django@qiliqili.in",
                      recipient_list=['kocio@vip.qq.com'])
            self.session.data.update({'record_count': 0})
            return "REC_CODE:%s\n收集完成" % debug_code
        record_count += 1
        self.session.data.update({'record_count': record_count})


class FgoHandler(AbstractHandler):
    star_name = {
        10: "[5★英灵]",
        9: "[5☆礼装]",
        8: "[4★英灵]",
        7: "[4☆礼装]",
        6: "[3★英灵]",
        5: "[3☆礼装]",
    }
    star = {
        10: ["アルトリア・ペンドラゴン", "アルテラ", "ギルガメッシュ", "諸葛孔明〔エルメロイⅡ世〕", "坂田金時", "ヴラド三世", "ジャンヌ・ダルク", "オリオン", "玉藻の前",
             "フランシス・ドレイク", "沖田総司", "スカサハ", "ジャック・ザ・リッパー", "モードレッド", "ニコラ・テスラ"],
        9: ["フォーマルクラフト", "イマジナリ・アラウンド", "リミテッド／ゼロオーバー", "カレイドスコープ", "ヘブンズ・フィール", "プリズマコスモス", "不夜の薔薇", "月女神の沐浴",
            "ムーンライト・フェスト", "黒の聖杯", "ハロウィン・プリンセス", "ハロウィン・プチデビル", "メイド・イン・ハロウィン", "月の勝利者", "もう一つの結末", "ぐだお", "ぐだぐだ看板娘",
            "2030年の欠片", "プレゼント・フォー・マイマスター", "ホーリーナイト・サイン", "五百年の妄執", "グランド・ニューイヤー", "モナ・リザ"],
        8: ["アルトリア・ペンドラゴン〔オルタ〕", "アルトリア・ペンドラゴン〔リリィ〕", "ネロ・クラウディウス", "ジークフリート", "シュヴァリエ・デオン", "エミヤ", "アタランテ",
            "エリザベート・バートリー", "マリー・アントワネット", "マルタ", "ステンノ", "カーミラ", "ヘラクレス", "ランスロット", "タマモキャット", "エリザベート・バートリー〔ハロウィン〕",
            "アン・ボニー＆メアリー・リード", "メディア〔リリィ〕", "織田信長", "アルトリア・ペンドラゴン〔サンタオルタ〕", "ナーサリー・ライム", "アルトリア・ペンドラゴン〔オルタ〕"],
        7: ["鋼の鍛錬", "原始呪術", "投影魔術", "ガンド", "緑の破音", "宝石魔術・対影", "優雅たれ", "虚数魔術", "天の晩餐", "天使の詩", "旅の始まり", "封印指定 執行者",
            "マグダラの聖骸布", "ムーニー・ジュエル", "一の太刀", "ハロウィン・アレンジメント", "コードキャスト", "打ち上げオーダー！", "概念礼装EXPカード：ノッブ", "騎士の矜持",
            "聖者の行進", "死霊魔術", "目覚めた意志", "ヒロイック・ニューイヤー", "ハッピー×3・オーダー"],
        6: ["マシュ・キリエライト", "ガイウス・ユリウス・カエサル", "ジル・ド・レェ", "ロビンフッド", "エウリュアレ", "クー・フーリン", "クー・フーリン〔プロトタイプ〕", "ロムルス",
            "メドゥーサ", "ブーディカ", "牛若丸", "アレキサンダー", "メディア", "ジル・ド・レェ", "メフィストフェレス", "クー・フーリン", "荊軻", "呂布奉先", "ダレイオス三世",
            "清姫", "ダビデ", "ヘクトール", "ディルムッド・オディナ", "フェルグス・マック・ロイ", "ヴァン・ホーエンハイム・パラケルスス", "チャールズ・バベッジ", "ヘンリー・ジキル＆ハイド"],
        5: ["アゾット剣", "偽臣の書", "青の黒鍵", "緑の黒鍵", "赤の黒鍵", "凛のペンダント", "魔導書", "龍脈", "魔術鉱石", "竜種", "葦の海", "ムーンセル・オートマトン",
            "ルーンストーン", "ジャック・オー・ランタン", "トリック・オア・トリート", "そして船は征く", "Fate ぐだぐだオーダー", "概念礼装EXPカード：おき太", "魔猪", "雷光のトナカイ君",
            "時計塔", "2016年の平穏", "ジャングルの掟"],
    }

    def get_cmd(self):
        return "fgo"

    def coin(self):
        if random.choice("01") == "0":
            return True
        else:
            return False

    def choice(self, start, end):
        start_len = len(self.star[start])
        end_len = len(self.star[end]) + start_len
        return random.randint(1, end_len) <= start_len

    def handle(self, data):
        card = []
        for y in range(0, 10):
            a = random.SystemRandom()
            d = a.random()
            count = None
            if d < 0.2:
                count = 7
            if d < 0.08:
                count = 8
            if d < 0.05:
                count = 9
            if d < 0.01:
                count = 10
            if not count:
                if self.choice(6, 5):
                    count = 5
                else:
                    count = 6
            card.append(count)
        black = True
        for a in card:
            if a in (10, 9, 8, 7):
                black = False
                break
        msg = "@%s\n" % data['SenderName']
        if black:
            msg += "酋长,您的保底到了.\n"
            card.pop(0)
            if self.coin():
                card.append(7)
            else:
                card.append(8)
        random.shuffle(card)
        if 10 in card:
            msg += "哇,欧皇. 凸^-^凸\n"
        for a in card:
            msg += self.star_name[a] + random.choice(self.star[a]) + "\n"
        return msg


class FeHandler(AbstractHandler):
    star_name = {
        7: "5☆ ",
        5: "5★ ",
        1: "4★ ",
        -1: "3★ ",
    }
    star = {
        7: ["塞利斯：光を継ぐ者 红/剑/步行", "尤利娅：神竜を继ぐ者 绿/魔/步行", "萨娜琪：ベグニオンの神使 红/魔/步行", "艾尔特夏：獅子王 红/剑/骑马", "奥尔艾恩：青の魔導騎士 蓝/魔/骑马",
            "莱因哈特：雷神の右腕 蓝/魔/骑马", "蕾贝卡：つつましき野花 无/弓/步行", "普莉希拉：深窓の姫君 无/杖/骑马", "卡雷尔：剣魔 红/剑/步行", "妮妮安：宿命の巫女 蓝/龙/步行",
            "春日库洛姆：春色の聖王 绿/斧/步行", "春日卡米拉：春色の暗夜王女 绿/魔道书/飞行", "春日露琪娜：春色の聖王女 蓝/魔道书/步行", "春日马库斯：春色の暗夜王子 蓝/枪/骑马",
            "阿鲁姆：予言の勇者 红/剑/步行", "卢卡：穏やかな皮肉屋 蓝/枪/步行", "艾菲：一途な恋心 无/弓/步行", "克莱尔：高飛車お嬢様 蓝/枪/飞行"],
        5: ["龙马：白夜の侍 红/剑/步行", "琳：草原の少女 红/剑/步行", "露琪娜：未来を知る者 红/剑/步行", "雷昂：闇の王子 红/魔/骑马", "芝琪（幼年）：神竜の巫女 红/龙/步行",
            "凯因：猛牛 红/剑/骑马", "神威（男）：未来を選びし王子 红/龙/步行", "库洛姆：新たなる聖王 红/剑/步行", "希达：タリスの王女 红/剑/飞行", "马尔斯：アリティアの王子 红/剑/步行",
            "罗伊：若き獅子 红/剑/步行", "萨莉雅：物陰の闇使い 红/魔/步行", "莉莉娜：美しき盟主 红/魔/步行", "赫克托耳：オスティアの勇将 绿/斧/重甲", "密涅瓦：赤い竜騎士 绿/斧/飞行",
            "卡米拉：妖艶な花 绿/斧/飞行", "西玛：グラの王女 绿/斧/重甲", "塞尔吉：竜好きの竜騎士 绿/斧/飞行", "珐：神とよばれし竜 绿/龙/步行", "霍克艾：砂漠の守護者 绿/斧/步行",
            "玛利克：風の魔導士 绿/魔/步行", "雷万：気高き傭兵 绿/斧/步行", "阿库娅：泉の歌姫 蓝/枪/步行", "日乃香：紅の戦姫 蓝/枪/飞行", "琳达：光の魔導士 蓝/魔/步行",
            "阿贝尔：黒豹 蓝/枪/骑马", "艾尔菲：怪力の重騎士 蓝/枪/重甲", "卡秋娅：白騎の次姉 蓝/枪/飞行", "缇雅莫：若き天才騎士 蓝/枪/飞行", "诺诺：永遠の幼子 蓝/龙/步行",
            "皮耶莉：殺戮本能 蓝/枪/骑马", "路弗雷（男）：謎多き軍師 蓝/魔/步行", "阳炎：古風な忍 无/暗/步行", "樱：慈しみの巫女 无/杖/步行", "乔卡：忠実なる執事 无/暗/步行",
            "乔治：大陸一の弓騎士 无/弓/步行", "玛莉娅：ミネルバの妹 无/杖/步行", "拓海：神弓の使い手 无/弓/步行", "伊弗列姆：碧空の勇王 蓝/枪/步行", "艾瑞柯：碧風の優王女 红/剑/步行",
            "艾莉泽：可憐な花 无/杖/步行", "奥古玛：タリスの傭兵 红/剑/步行", "克莱因：銀の貴公子 无/弓/步行", "拉克西丝：獅子王の妹姫 无/杖/步行", "露西亚：柔らかな光 无/杖/步行",
            "贾法尔：死神 无/暗/步行"],
        1: ["凯因：猛牛 红/剑/骑马", "神威（男）：未来を選びし王子 红/龙/步行", "库洛姆：新たなる聖王 红/剑/步行", "希达：タリスの王女 红/剑/飞行", "马尔斯：アリティアの王子 红/剑/步行",
            "罗伊：若き獅子 红/剑/步行", "萨莉雅：物陰の闇使い 红/魔/步行", "莉莉娜：美しき盟主 红/魔/步行", "艾利乌德：リキア一の騎士 红/剑/骑马", "奥莉薇：恥ずかしがり屋の 红/剑/步行",
            "风花：お転婆侍 红/剑/步行", "索尔：碧の騎士 红/剑/骑马", "杜卡：アリティア重騎士 红/剑/重甲", "帕奥拉：白騎の長姉 红/剑/飞行", "日向：破天荒な侍 红/剑/步行",
            "菲尔：剣聖をつぐ者 红/剑/步行", "亨利：壊れた心の 红/魔/步行", "拉兹瓦尔德：花咲く笑顔 红/剑/步行", "露娜：秘めた憧憬 红/剑/步行", "隆库：女嫌いの剣士 红/剑/步行",
            "索菲亚：ナバタの預言者 红/魔/步行", "雷伊：闇の申し子 红/魔/步行", "芝琪（成年）：神竜の巫女 红/龙/步行", "卡米拉：妖艶な花 绿/斧/飞行", "西玛：グラの王女 绿/斧/重甲",
            "塞尔吉：竜好きの竜騎士 绿/斧/飞行", "珐：神とよばれし竜 绿/龙/步行", "霍克艾：砂漠の守護者 绿/斧/步行", "玛利克：風の魔導士 绿/魔/步行", "雷万：気高き傭兵 绿/斧/步行",
            "君特：老騎士 绿/斧/骑马", "塞西莉亚：王国の娘 绿/魔/骑马", "妮诺：魔道の申し子 绿/魔/步行", "巴兹：タリスの義勇兵 绿/斧/步行", "巴特尔：怒れる闘士 绿/斧/步行",
            "哈罗鲁德：不運なヒーロー 绿/斧/步行", "弗雷德里克：穏和な騎士団長 绿/斧/骑马", "贝尔卡：殺し屋 绿/斧/飞行", "阿贝尔：黒豹 蓝/枪/骑马", "艾尔菲：怪力の重騎士 蓝/枪/重甲",
            "卡秋娅：白騎の次姉 蓝/枪/飞行", "缇雅莫：若き天才騎士 蓝/枪/飞行", "诺诺：永遠の幼子 蓝/龙/步行", "皮耶莉：殺戮本能 蓝/枪/骑马", "路弗雷（男）：謎多き軍師 蓝/魔/步行",
            "温蒂：可憐な重騎士 蓝/枪/重甲", "艾丝特：白騎の末妹 蓝/枪/飞行", "奥丁：力を封印せし者 蓝/魔/步行", "胧：魔王顔の 蓝/枪/步行", "神威（女）：未来を選びし王女 蓝/龙/步行",
            "杰刚：マルスの軍師 蓝/枪/骑马", "夏妮：朗らかな天馬騎士 蓝/枪/飞行", "索瓦蕾：紅の騎士 蓝/枪/骑马", "椿：完璧主義 蓝/枪/飞行", "东尼：村人 蓝/枪/步行",
            "芙萝利娜：可憐な天馬騎士 蓝/枪/飞行", "阳炎：古風な忍 无/暗/步行", "樱：慈しみの巫女 无/杖/步行", "乔卡：忠実なる執事 无/暗/步行", "乔治：大陸一の弓騎士 无/弓/步行",
            "玛莉娅：ミネルバの妹 无/杖/步行", "浅间：飄々とした僧 无/杖/步行", "维奥尔：貴族的な弓使い 无/弓/步行", "盖亚：お菓子好き盗賊 无/暗/步行", "克莱丽奈：気ままな姫将軍 无/杖/骑马",
            "哥顿：アリティアの弓兵 无/弓/步行", "才藏：爆炎使い 无/暗/步行", "塞拉：かしましシスター 无/杖/步行", "刹那：ぼんやり 无/弓/步行", "杰洛：加虐性癖 无/弓/步行",
            "菲莉茜娅：ドジメイド 无/暗/步行", "马修：義の盗賊 无/暗/步行", "莉兹：飛び跳ねシスター 无/杖/步行", "里弗：僧侶 无/杖/步行", "艾莉泽：可憐な花 无/杖/步行",
            "奥古玛：タリスの傭兵 红/剑/步行", "克莱因：銀の貴公子 无/弓/步行", "拉克西丝：獅子王の妹姫 无/杖/步行", "露西亚：柔らかな光 无/杖/步行", "贾法尔：死神 无/暗/步行",
            "那巴尔：紅の剣士 红/剑/步行", "米歇尔：野望の王 绿/斧/飞行"],
        -1: ["艾利乌德：リキア一の騎士 红/剑/骑马", "奥莉薇：恥ずかしがり屋の 红/剑/步行", "风花：お転婆侍 红/剑/步行", "索尔：碧の騎士 红/剑/骑马", "杜卡：アリティア重騎士 红/剑/重甲",
             "帕奥拉：白騎の長姉 红/剑/飞行", "日向：破天荒な侍 红/剑/步行", "菲尔：剣聖をつぐ者 红/剑/步行", "亨利：壊れた心の 红/魔/步行", "拉兹瓦尔德：花咲く笑顔 红/剑/步行",
             "露娜：秘めた憧憬 红/剑/步行", "隆库：女嫌いの剣士 红/剑/步行", "索菲亚：ナバタの預言者 红/魔/步行", "雷伊：闇の申し子 红/魔/步行", "芝琪（成年）：神竜の巫女 红/龙/步行",
             "那巴尔：紅の剣士 红/剑/步行", "君特：老騎士 绿/斧/骑马", "塞西莉亚：王国の娘 绿/魔/骑马", "妮诺：魔道の申し子 绿/魔/步行", "巴兹：タリスの義勇兵 绿/斧/步行",
             "巴特尔：怒れる闘士 绿/斧/步行", "哈罗鲁德：不運なヒーロー 绿/斧/步行", "弗雷德里克：穏和な騎士団長 绿/斧/骑马", "贝尔卡：殺し屋 绿/斧/飞行", "纳西恩：三竜将 绿/斧/飞行",
             "安娜：特務機関の隊長 绿/斧/步行", "路弗雷（男）：謎多き軍師 蓝/魔/步行", "温蒂：可憐な重騎士 蓝/枪/重甲", "艾丝特：白騎の末妹 蓝/枪/飞行", "奥丁：力を封印せし者 蓝/魔/步行",
             "胧：魔王顔の 蓝/枪/步行", "神威（女）：未来を選びし王女 蓝/龙/步行", "杰刚：マルスの軍師 蓝/枪/骑马", "夏妮：朗らかな天馬騎士 蓝/枪/飞行", "索瓦蕾：紅の騎士 蓝/枪/骑马",
             "椿：完璧主義 蓝/枪/飞行", "东尼：村人 蓝/枪/步行", "芙萝利娜：可憐な天馬騎士 蓝/枪/飞行", "夏洛恩：アスク王国の王女 蓝/枪/步行", "浅间：飄々とした僧 无/杖/步行",
             "维奥尔：貴族的な弓使い 无/弓/步行", "盖亚：お菓子好き盗賊 无/暗/步行", "克莱丽奈：気ままな姫将軍 无/杖/骑马", "哥顿：アリティアの弓兵 无/弓/步行", "才藏：爆炎使い 无/暗/步行",
             "塞拉：かしましシスター 无/杖/步行", "刹那：ぼんやり 无/弓/步行", "杰洛：加虐性癖 无/弓/步行", "菲莉茜娅：ドジメイド 无/暗/步行", "马修：義の盗賊 无/暗/步行",
             "莉兹：飛び跳ねシスター 无/杖/步行", "里弗：僧侶 无/杖/步行", "路弗雷（女）：謎多き軍師 绿/魔/步行", "阿尔冯斯：アスク王国の王子 红/剑/步行", "乌露斯拉：蒼鴉 蓝/魔/骑马",
             "米歇尔：野望の王 绿/斧/飞行"],
    }
    rank = {
        -5: "哇！金色传说大酋长！",
        -4: "哇！史诗大酋长！",
        -3: "大酋长！",
        -2: "酋长！",
        -1: "凡骨！",
        0: "手气欠佳",
        3: "手气不错",
        1: "手气一般",
        5: "欧洲人！",
        7: "欧洲精英！",
        9: "欧洲贵族！",
        11: "欧洲大佬",
        13: "欧巨佬！",
        21: "欧皇！",
        35: "哇！欧神显圣！"
    }

    def get_cmd(self):
        return "fe"

    def choice(self, start, end):
        start_len = len(self.star[start])
        end_len = len(self.star[end]) + start_len
        return random.randint(1, end_len) <= start_len

    def handle(self, data):
        card = []
        for y in range(0, 5):
            a = random.SystemRandom()
            d = a.random()
            count = -1
            if d < 0.42:
                count = 1
            if d < 0.06:
                count = 5
            if d < 0.03:
                count = 7
            card.append(count)
        msg = "@%s\n" % data['SenderName']
        random.shuffle(card)
        for a in card:
            msg += self.star_name[a] + random.choice(self.star[a]) + "\n"
        power = sum(card)
        if power in self.rank:
            msg += self.rank[power]
        msg += "   欧能：%s" % power
        return msg


class ClearSessionHandler(AbstractHandler):
    def get_cmd(self):
        return "clear_session"

    def handle(self, data):
        self.session.clear()
        return 'ACK'
