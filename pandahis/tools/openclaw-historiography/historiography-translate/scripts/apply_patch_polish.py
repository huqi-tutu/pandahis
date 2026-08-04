#!/usr/bin/env python3
"""人工润色 _patch_output：去重、过渡，不增删段落。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List

PATCH_DIR = Path(
    "/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis/data/"
    "11新标注条目翻译/待补全段落翻译/_patch_output"
)


def split_paras(text: str) -> List[str]:
    parts = [p.strip() for p in text.split("\n\n")]
    return [p for p in parts if p]


def join_paras(paras: List[str]) -> str:
    return "\n\n".join(paras)


def set_para(paras: List[str], idx: int, new: str) -> None:
    paras[idx] = new.strip()


FixFn = Callable[[List[str]], None]

FIXES: Dict[str, FixFn] = {}


def fix(name: str):
    def deco(fn: FixFn) -> FixFn:
        FIXES[name] = fn
        return fn

    return deco


@fix("GLBL_00038_周穆王.json")
def _(ps):
    # P13 enrich 与基稿末段整段重复，改为简短收束
    set_para(
        ps,
        -2,
        "穆王西巡、造父驾车与《穆天子传》所铺陈的瑶池之会，属后世传奇叙事，与《周本纪》正史另成一脉；若读者好奇其细节，可另参《穆天子传》及《秦本纪》《赵世家》相关记载。",
    )


@fix("GLBL_00058_帝辛（纣）.json")
def _(ps):
    # P31 enrich 重复，P30 已补武庚后续
    set_para(
        ps,
        -2,
        "《论语·子张》中子贡则留下一句冷峻的观察：「纣之不善，不如是之甚也。是以君子恶居下流，天下之恶皆归焉。」——失败者往往承担超出本分的骂名，这本身也是历史书写的一部分。",
    )


@fix("GLBL_00096_禹.json")
def _(ps):
    # P42 删与 P41 重复的启即位句义，保留吴越春秋增量
    set_para(
        ps,
        -2,
        "关于禹的后续，《吴越春秋·越王无余外传》里还记了一个很动人的细节。禹在治水途中，有一次遇见了押送的罪人，他下车对着罪人哭泣。身边人觉得奇怪，禹说：尧舜那个时候，天下人都以尧舜的心为自己的心；如今我做君王，老百姓却各有私心、各怀异志，我能不痛心吗？这个画面，与《史记》评价他的「其德不违，其仁可亲」相互呼应，也让人看到这位铁面治水、律令如山的君王，内心最柔软的那一面。",
    )


@fix("GLBL_00147_魏文侯.json")
def _(ps):
    # 去掉「前置引入」残片；P18 enrich 重复
    intro, _, body = ps[1].partition("---，正文，")
    ps[0] = intro.strip()
    ps[1] = body.strip()
    set_para(
        ps,
        -2,
        "魏文侯一生，武功上连年扩张、修筑防线，文治上广纳贤才、打造西河学派，用人上既能放手让乐羊啃下中山，也能在魏成子与翟璜之间做出超越业务层面的决断。战国初年拼的不只是兵甲土地，更是谁手里有好用的人——文侯攒下的这份家底，让魏国在惠王之前一直保持着霸主成色。",
    )


@fix("GLBL_00429_范睢.json")
def _(ps):
    set_para(
        ps,
        -2,
        "蔡泽入秦之后，范睢的政治生涯还将迎来新的转折；但就本传此刻的叙事而言，恩仇已报、相位坐稳，正是他权势的顶点。",
    )


@fix("GLBL_00718_楚灵王.json")
def _(ps):
    set_para(
        ps,
        -2,
        "楚灵王从弑君夺位到饿死荒山，不过十二三年。伍举在申地会盟时提醒的前车之鉴——夏桀、商纣、周幽王——最终也在他身上应验：鼎盛之时埋下的种子，往往在最不可一世的时候发芽。",
    )


@fix("GLBL_00148_魏武侯.json")
def _(ps):
    # P3 与 P2 重复介绍文侯卒、武侯立
    set_para(
        ps,
        2,
        "武侯即位的第一年，东边的赵国先出了变故。赵敬侯刚刚坐上国君的位子，公室里的公子朔就起兵作乱。政变没能成功，公子朔在赵国站不住脚，一口气跑到了魏国。人虽然落了难，带来的见面礼却是一个军事方案——说服魏国联合出兵，去偷袭赵国的都城邯郸。不过，这一仗打得并不顺手，魏军吃了败仗，只能撤退。到了第二年（前385年），刀兵之外，魏武侯得先把自家地盘夯结实。这一年，魏国在安邑（今山西夏县西北）和王垣两处大兴土木，修筑城池。",
    )


@fix("GLBL_00696_卫庄公.json")
def _(ps):
    set_para(
        ps,
        1,
        "杨即位后，史家着墨不多，但在位二十三年里，最大的隐患来自继承人安排——对庶子州吁毫无底线的纵容，加上把大夫石碏的逆耳忠言当耳边风，亲手给儿子卫桓公的悲剧写好了剧本。庄公五年，他从齐国娶了一位女子做正妻。这位齐女很受宠爱，但多年下来，肚子始终没有动静。后来庄公又娶了陈国女子为夫人。陈女生下一个儿子，可惜这孩子命短，『蚤（通『早』）死』——很早就夭折了。陈女的妹妹同样得到了庄公的宠幸，生下了儿子完。完的生母去世后，庄公让正妻齐女把完收养过来，立为太子。庄公还有一位受宠的爱妾，生下了儿子州吁。到庄公十八年，州吁长大成人，喜好军事，庄公便让他带兵统将。",
    )


@fix("GLBL_00061_晋悼公.json")
def _(ps):
    # P2 过渡，删末尾迎周立君；P3/P4 去重分工
    set_para(
        ps,
        1,
        "要弄清晋悼公如何即位，须先回看前朝最后一幕。晋厉公诛杀郤氏后，不但没有安抚卿族，反而向栾书等人宣示郤氏之罪，轻描淡写地让他们“官复原职”。栾书与中行偃表面叩头谢恩，暗中已在谋划反击。厉公随即提拔亲信胥童为卿，进一步激化了矛盾。闰月乙卯，厉公前往匠骊氏家中游玩，栾书、中行偃趁机率党羽突袭，将他逮捕囚禁，并杀死胥童。",
    )
    set_para(
        ps,
        2,
        "正月庚申日，栾书、中行偃正式弑杀晋厉公。更过分的是，他们仅用了一乘车陪葬——这对诸侯来说，是严重降格的薄葬，几乎是在抹去他作为国君的最后体面。《左传·成公十八年》补充了这场政变的背景：厉公在位后期宠信胥童等近臣，试图削弱卿族势力，结果逼反了栾书、中行偃，最终沦为阶下囚，丢了性命。",
    )
    set_para(
        ps,
        3,
        "厉公被囚禁六天后死去。死后第十天，也就是庚午日，大夫智罃前往周都雒邑，将公子周迎接回晋国。一行人抵达都城绛邑，杀鸡与群臣大夫盟誓，正式拥立公子周为国君。这便是晋悼公。辛巳日，悼公前往武公之庙朝拜，告慰先祖。到了二月乙酉日，正式即位。",
    )


@fix("GLBL_00073_武丁.json")
def _(ps):
    set_para(
        ps,
        2,
        "接下来要说的，是武丁中兴路上一次看似偶然、实则关键的转折——祭祀中「飞雉登鼎」的异象。",
    )
    set_para(
        ps,
        3,
        "要理解这一异象为何令武丁如此震动，须先略知商代「先鬼后礼」的祭祀观念。",
    )
    set_para(
        ps,
        4,
        "《礼记·表记》载，殷人尊崇鬼神，把神灵放在第一位，把礼制放在第二位——「殷人尊神，率民以事神，先鬼而后礼」。大到打仗迁都，小到刮风下雨，商王都得通过占卜来揣测老天爷的意图。那些祭祀用的大鼎，更是沟通天地鬼神的圣物，不是一般的锅碗瓢盆。",
    )


@fix("GLBL_00442_虞卿.json")
def _(ps):
    set_para(
        ps,
        0,
        "在战国中后期那片混乱的棋局里，秦国已经成了独霸一方的狠角色，而赵国，几乎是关东六国中唯一还能在军事上硬扛强秦的国家。也正是在这国家命运风云变幻的节骨眼上，出了一位极有远见却又让后世读来感到惋惜的谋臣——虞卿。",
    )


@fix("GLBL_00746_韩釐王.json")
def _(ps):
    set_para(
        ps,
        0,
        "战国到了中后期，列国之间的纵横捭阖已经进入了白热化阶段。夹在秦、赵、魏几大强国之间的韩国，日子尤其难过，几乎成了别人案板上的鱼肉。要理解韩釐王二十三年那场华阳之围，须先回到他即位之初。",
    )
    set_para(ps, 1, "襄王去世后，太子咎即位，这就是韩釐王。")
    ps[2] = (
        ps[2].rstrip("。")
        + "。二十三年，赵、魏联军重兵直扑华阳，韩国急派使臣往秦求救，秦昭襄王与穰侯魏冉却按兵不动，摆明了坐山观虎斗。"
    )


@fix("GLBL_00057_帝喾.json")
def _(ps):
    set_para(
        ps,
        -2,
        "帝喾的配偶不止一位：陈锋氏生放勋，娵訾氏生挚。挚继位后治理不善，最终由弟放勋继立，这就是后世所称的帝尧。",
    )


@fix("GLBL_00421_管仲.json")
def _(ps):
    set_para(
        ps,
        -2,
        "管仲个人的富贵，几乎可以和王室比肩，家里建有三归台，堂上设有反坫，这些本是诸侯之礼，但齐国人并不认为他越制奢侈。这样过了一百多年，齐国又出了一位晏子。",
    )


@fix("GLBL_00704_宋文公.json")
def _(ps):
    set_para(
        ps,
        -2,
        "文公之子共公瑕继位。从这时起，宋国开始实行厚葬。当时的君子因此批评执政的华元，认为他没有尽到臣子劝谏的本分，未能阻止这种僭越礼制的做法。",
    )


@fix("GLBL_00736_郑简公.json")
def _(ps):
    set_para(
        ps,
        -2,
        "简公三十六年卒，子姬宁立，是为郑定公。",
    )


@fix("GLBL_00068_楚庄王.json")
def _(ps):
    set_para(
        ps,
        1,
        "穆王之后，楚国在春秋中期迎来了一位让整个中原屏住呼吸的霸主。楚庄王接手楚国的时候才二十岁左右，按《史记·楚世家》的记法，他刚即位时，楚国在列国中的分量已经不小，但中原那些老牌诸侯，仍时常带着几分南蛮偏见的目光打量这个南方大国。",
    )


@fix("GLBL_00052_宋景公.json")
def _(ps):
    # P11 新补昭公，避免与 P10「景公去世」重复起笔
    if ps[-2].startswith("景公去世后"):
        set_para(
            ps,
            -2,
            ps[-2].replace("景公去世后，", "", 1),
        )


@fix("GLBL_00062_晋文公.json")
def _(ps):
    # P53 围郑叙述与 P54–P55 内部重复
    set_para(
        ps,
        52,
        "到了晋文公七年，秦晋两国又联手了。晋文公和秦穆公联合出兵包围郑国，算的是两笔旧账：一是当年重耳流亡路过郑国时，郑文公对他无礼；二是城濮之战时，郑国曾出兵帮助楚国。包围圈一收紧，晋文公点名要一个人，就是当年那位建议郑文公要么礼遇重耳、要么干脆杀了他的叔瞻。叔瞻听到风声，干脆自杀了。郑国把他的尸体交给晋国，本以为能了事。",
    )
    set_para(
        ps,
        53,
        "可晋文公根本不买账：「光一个叔瞻不够。必须把郑伯本人交出来，才能解我心头之恨。」这话一出来，郑国上下是真怕了。打又打不过，交出国君更不可能——怎么办？",
    )


def apply_file(path: Path) -> bool:
    fn = FIXES.get(path.name)
    if not fn:
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    ps = split_paras(data["翻译详情"])
    before = list(ps)
    fn(ps)
    if ps == before:
        print(f"  [skip] {path.name} unchanged")
        return False
    data["翻译详情"] = join_paras(ps)
    meta = data.setdefault("_patch_meta", {})
    meta["polished_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat()
    meta["polish_note"] = "manual dedup/transition, paragraph count preserved"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  [ok] {path.name}")
    return True


def main() -> None:
    n = 0
    for path in sorted(PATCH_DIR.glob("GLBL_*.json")):
        if apply_file(path):
            n += 1
    print(f"\nPolished {n} files.")


if __name__ == "__main__":
    main()
