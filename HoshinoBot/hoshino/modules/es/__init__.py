#encoding:utf-8
import os, random, re, pprint, json, math, asyncio, threading
import traceback
from io import BytesIO
from PIL import Image
from collections import defaultdict
from datetime import datetime
import nonebot
from hoshino import R, Service, priv, util
from hoshino.typing import *
from hoshino.util import DailyNumberLimiter
from .es import Gacha
from urllib import request

working_path = "hoshino/modules/es/"
img_path = "./images"
char_data = json.load(open(working_path + "character_table.json", encoding="utf-8"))
gacha_data = json.load(open(working_path + "config.json", encoding="utf-8"))

sv_help = '''
[ES十连] [ES当前卡池] [ES切换卡池] [ES历史卡池]
'''.strip()
sv = Service('es', help_=sv_help, bundle="es", enable_on_default=True)

jewel_limit = DailyNumberLimiter(2)
jing_limit = DailyNumberLimiter(2)

JEWEL_EXCEED_NOTICE = f"您已抽{jewel_limit.max}次十连，欢迎明天再来！"
JING_EXCEED_NOTICE = f"您已井{jing_limit.max}次，欢迎明天再来！"

group_banner = {}
try:
    group_banner = json.load(open(working_path + "group_banner.json", encoding="utf-8"))
except FileNotFoundError: pass
    
def save_group_banner():
    with open(working_path + "group_banner.json", "w", encoding="utf-8") as f:
        json.dump(group_banner, f, ensure_ascii=False)
        
def ak_group_init(gid):
    group_banner[gid] = { "banner": "【浮现的缤纷色彩】月永雷欧"}
        
@sv.on_fullmatch(("ES当前卡池"))
async def gacha_info(bot, ev: CQEvent):
    gid = str(ev.group_id)
    if not gid in group_banner:
        ak_group_init(gid)
    banner = group_banner[gid]["banner"]
    gacha = Gacha()
    gacha.set_banner(banner)
    line = gacha.explain_banner()
    await bot.send(ev, line)

@sv.on_prefix(("ES切换卡池"))
async def set_pool(bot, ev: CQEvent):
    name = util.normalize_str(ev.message.extract_plain_text())
    if not name:
        # 列出当前卡池
        current_time=datetime.now().timestamp()
        list_cur=[]
        for gacha in gacha_data["banners"]:
            if int(gacha_data["banners"][gacha]["end"])>int(current_time):
                list_cur.append(gacha)
        if list_cur:
            lines = ["当期卡池:"] + list_cur + ["", "使用命令[ES切换卡池 （卡池名）]进行设置","使用命令[ES历史卡池]查看全部往期卡池"]
            await bot.finish(ev, "\n".join(lines))
        else:
            await bot.finish(ev, "未找到正在进行中的卡池……请联系维护组更新卡池信息或使用命令[ES历史卡池]查看全部往期卡池")
    else:
        if name in gacha_data["banners"].keys():
            gid = str(ev.group_id)
            group_banner[gid]["banner"] = name
            save_group_banner()
            await bot.send(ev, f"卡池已经切换为 {name}", at_sender=True)
            await gacha_info(bot, ev)
        else:
            await bot.finish(ev, f"没找到卡池: {name}")
            
@sv.on_fullmatch(("ES历史卡池"))
async def history_pool(bot, ev: CQEvent):
    lines = ["全部卡池:"] + list(gacha_data["banners"].keys()) + ["", "使用命令 ES切换卡池 x（x为卡池名）进行设置"]
    await bot.finish(ev, "\n".join(lines))

async def check_jewel_10(bot, ev):
    if not jewel_limit.check(ev.user_id):
        await bot.finish(ev, JEWEL_EXCEED_NOTICE, at_sender=True)

async def check_jewel_300(bot, ev):    
    if not jing_limit.check(ev.user_id):
        await bot.finish(ev, JING_EXCEED_NOTICE, at_sender=True)

@sv.on_prefix(("ES十连"), only_to_me=False)
async def gacha_10(bot, ev: CQEvent):
    gid = str(ev.group_id)
    if not gid in group_banner:
        ak_group_init(gid)
    b = group_banner[gid]["banner"]
    
    # barrier
    await check_jewel_10(bot, ev)
    jewel_limit.increase(ev.user_id, 1)
    
    g = Gacha()
    g.set_banner(b)
    g.rare_chance = False
    result = g.ten_pull()
    await bot.send(ev, g.summarize_tenpull(result), at_sender=True)
    
    for x in result:
        if x['star']==6:
            print(x['char'])
            img = MessageSegment.image(f'file:///{os.path.abspath(working_path + x["char"]+".png")}')
            line = f'{img}'
            await bot.send(ev, line)
    

@sv.on_prefix(("ES一井"), only_to_me=False)
async def gacha_300(bot, ev: CQEvent):
    gid = str(ev.group_id)
    if not gid in group_banner:
        ak_group_init(gid)
    b = group_banner[gid]["banner"]
    
    # barrier
    await check_jewel_300(bot, ev)
    jing_limit.increase(ev.user_id, 1)
    
    g = Gacha()
    g.set_banner(b)
    g.rare_chance = False
    result = g.jing_pull()
    await bot.send(ev, g.summarize_jing_pull(result), at_sender=True)
    

def save_pic(url):
    filename = working_path + "cache/" + os.path.basename(url)
    if os.path.exists(filename):
        print("save_pic: file exists - %s" % filename)
    else:
        resp = request.urlopen(url)
        img = resp.read()
        filename = working_path + "cache/" + os.path.basename(url)
        print("save_pic %s" % filename)
        with open(filename, "wb+") as f:
            f.write(img)
    return filename