#encoding:utf-8
import pprint, json, random, copy, math, os
from io import BytesIO
from PIL import Image
from nonebot import MessageSegment
from hoshino import R
from hoshino.config import RES_DIR
from hoshino.util import pic2b64

working_path = os.path.abspath(os.path.realpath(os.path.dirname(__file__)))
#working_path=""
img_path = os.path.join(RES_DIR, "img","akgacha")  

char_data = {}
gacha_data = {}

def data_init():
    global char_data,gacha_data
    char_data = json.load(
        open(os.path.join(working_path, "character_table.json"), encoding="utf-8"))
    gacha_data = json.load(
        open(os.path.join(working_path, "config.json"), encoding="utf-8"))

data_init()

probs = {
    "up_6": 50,
    "other_6": 50,
    "up_5": 50,
    "other_5": 50,
    "up_4": 20,
    "other_4": 80,
    "limited_up_6": 70,
    "star_6": 2,
    "star_5": 8,
    "star_4": 50,
    "star_3": 40
}

def get_charid(name):
    ret = [k for k in char_data.keys() if char_data[k]["name"] == name]
    return ret[0] if len(ret) > 0 else None

def roll(n):
    return random.randint(0, n-1)

def pull_naive(rate_6=2, limited=False, must_rare=False):
    star = 3
    up = False
    
    x1 = roll(100)
    if x1 < rate_6:
        x2 = roll(100)
        star = 6
        if limited == True: # "r6" != True
            up = (x2 < probs["limited_up_6"])
        else:
            up = (x2 < probs["up_6"])
    else:
        x2 = roll(98)
        x3 = roll(100)
        if must_rare or x2 < probs["star_5"]:
            star = 5
            up = (x3 < probs["up_5"])
        elif x2 < probs["star_5"] + probs["star_4"]:
            star = 4
            up = (x3 < probs["up_4"])
        else:
            pass # 3-star
    return { "star": star, "up": up }
    
# learn from HoshinoBot
def gen_team_pic(team, size=128, ncol=5):
    nrow = math.ceil(len(team)/ncol)
    des = Image.new("RGBA", (ncol * size, nrow * size), (0,0,0, 0))
    for i, name in enumerate(team):
        face = Image.open(os.path.join(img_path, f"{get_charid(name)}.png"),).convert("RGBA").resize((size, size), Image.LANCZOS)
        x = i % ncol
        y = math.floor(i / ncol)
        des.paste(face, (x * size, y * size), face)
    return des

def img_segment(img):
    return MessageSegment.image(pic2b64(img))
    
class Gacha:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.count = {}
        self.char_count = {}
        self.result_list = []
        self.rare_list = { 5: [], 6: [] }
        self.rare_chance = True
        self.nth = 0
        self.nth_target = 0
        self.nth_favor = 0
        self.n6count = 0
        self.up5_name = None
        self.tenjou = False
    
    def set_banner(self, b):
        self.banner = gacha_data["banners"][b]
        self.banner["name"] = b
        self.pool = {}
        for key in ["up_6", "up_5", "up_4"]:
            self.pool[key] = self.banner[key]
        exclude = self.banner["up_6"] + self.banner["up_5"] + self.banner["up_4"] + self.banner["exclude"]
        for key in ["star_6", "star_5", "star_4", "star_3"]:
            self.pool[key] = [x for x in gacha_data["pool"][key] if x not in exclude]
        if self.banner.get("multi", None): # ??????????????????
            for key in self.banner["multi"].keys():
                id = get_charid(key)
                rarity = "star_%d" % (char_data[id]["rarity"] + 1)
                n = self.banner["multi"][key]
                print(id, rarity, n)
                self.pool[rarity] += [key] * n
                print(self.pool[rarity])                
    
    def explain_banner(self):
        main_up = self.banner["up_6"]
        other_up = self.banner["up_5"] + self.banner["up_4"]
        if self.banner.get("multi", None):
            other_up += list(self.banner["multi"].keys())
        if len(main_up) == 0:
            main_up = self.banner["up_5"]
            other_up = self.banner["up_4"]
        main_pic = gen_team_pic(main_up, 72, len(main_up))
        other_pic = gen_team_pic(other_up, 72, len(other_up)) if len(other_up) > 0 else None
        banner_name = self.banner["name"]
        if banner_name == "??????": banner_name += " #%d" % self.banner["id"]
        lines = []
        lines.append(f"????????????: {banner_name}")
        if self.banner["limited"] == True: lines.append("(?????????)")
        # print(img_segment(main_pic))
        lines.append(f"????????????: {' '.join(main_up)}")
        lines.append(f"{img_segment(main_pic)}")
        if other_pic:
            lines.append(f"??????up??????: {' '.join(other_up)}")
            lines.append(f"{img_segment(other_pic)}")
        if self.banner["no_other_6"]:
            lines.append("?????????up???5/6????????????????????????????????????")
        if self.banner["favor"]:
            lines.append(f"????????????: {self.banner['favor']}")
        if len(self.banner["up_6"]) > 0:
            rate = probs["limited_up_6"] if self.banner["limited"] == True else probs["up_6"]
            lines.append(f"up???????????? {rate/50}%, 6??????????????? 2%")
        else:
            rate = probs["up_5"]
            lines.append(f"up???????????? {rate*8/100}%, 6??????????????? 2%")
        if self.banner.get("note", None):
            lines.append("??????: %s"  % self.banner["note"])
        return "\n".join(lines)
        

    def rate_6(self):
        return 2 if self.n6count < 50 else 2 * (self.n6count - 49)
        
    def pull(self):
        self.nth += 1
        # ?????????
        if (self.nth >= 10 and self.rare_chance):
            result = pull_naive(self.rate_6(), self.banner["limited"], True)
            result["??????"] = True
        else:
            result = pull_naive(self.rate_6(), self.banner["limited"], False)
        # ????????????
        if self.banner["no_other_6"] and result["star"] >= 4: result["up"] = True
        # ??????
        char_key = "%s_%d" % ("up" if result["up"] else "star", result["star"])
        if len(self.pool[char_key]) == 0:
            result["up"] = False
            char_key = "star_%d" % result["star"]
        result["char"] = cname = random.sample(self.pool[char_key], 1)[0]
        
        # 6???????????????
        if self.banner.get("tenjou", None):
            tenjou = self.banner["tenjou"]
            if self.nth == tenjou["n"] and not self.char_count.get(tenjou["name"], None):
                print(f"?????? - {tenjou['n']}")
                result = { "char": tenjou["name"], "star": 6, "up": True, "tenjou": True }
                cname = tenjou["name"]
                self.tenjou = True
        # 5?????????
        if result["star"] == 5 and self.banner.get("tenjou_5", None) and self.up5_name != "used":
            if char_key == "up_5" and not self.up5_name:
                self.up5_name = cname # ???????????????up5?????????
            elif self.up5_name:
                print("??????up5?????????")
                result["char"] = cname = random.sample([x for x in self.pool["up_5"] if x != self.up5_name], 1)[0]
                self.up5_name = "used"
                
        self.result_list.append(cname)
        
        # ??????????????????
        type = ("up_%d" if result["up"] else "other_%d") % result["star"]
        self.count[type] = self.count.get(type, 0) + 1
        self.count[result["star"]] = self.count.get(result["star"], 0) + 1
        # ??????????????????up??????
        if (type=="up_6" or (len(self.pool["up_6"])==0 and type=="up_5")) and self.nth_target == 0:
            self.nth_target = self.nth
        if self.banner["favor"] and cname == self.banner["favor"] and self.nth_favor == 0:
            self.nth_favor = self.nth
        # ????????????
        self.char_count[cname] = self.char_count.get(cname,
            { "id": get_charid(cname), "star": result["star"], "count": 0 })
        self.char_count[cname]["count"] += 1
        # ??????????????????
        if self.n6count >= 50:
            result["rate_6"] = self.rate_6()
        # ??????????????????   
        if result["star"] >= 5:
            self.rare_chance = False
            self.rare_list[result["star"]].append(cname)
        # ???????????????
        if result["star"] == 6:
            print(result)            
            if self.n6count >= 50:
                print("????????? - %d" % (self.n6count+1))
                result["?????????"] = True
            self.n6count = 0
        else:
            self.n6count += 1
        return result
    
    def ten_pull(self):
        return [self.pull() for x in range(0, 10)]
        
    def count_tickets(self):
        green = yellow = 0
        for ch in self.char_count.values():
            g = y = 0
            s = ch["star"]
            c = ch["count"]
            c2 = min(max(c-1, 0), 5)
            c7 = max(c-6, 0)
            
            if s == 3:
                g = 10*c # 3??????????????????
            elif s == 4:
                g = 30 * c2
                y = 1 + c7
            elif s == 5:
                y = 1 + c2*5 + c7*13
            elif s == 6:
                y = 1 + c2*10 + c7*25
            #ch["green"] = g
            #ch["yellow"] = y
            green += g
            yellow += y
        return (green, yellow)
    
    def summarize(self, show_5star=False):
        pic = gen_team_pic(self.rare_list[6]) if not show_5star else gen_team_pic(self.rare_list[6] + self.rare_list[5])
        text = ["????????????:"]
        text.append(f"{img_segment(pic)}")
        text.append("???6??%d ???5??%d ???4??%d ???3??%d" % (self.count[6], self.count[5], self.count[4], self.count[3]))
        text.append("??????????????%d???????????%d???" % self.count_tickets())
        if self.nth_target > 0:
            line = "???%d???????????????up??????" % self.nth_target
            if self.banner["favor"] and self.nth_favor > 0:
                if self.nth_favor > self.nth_target or self.nth_favor == 0:
                    line += "???????????????"
                line += "\n???%d???????????????????????????" % self.nth_favor
            text.append(line)
        else:
            text.append("up????????????up??????")

        # ??????
        judge = self.nth_favor if self.banner["favor"] else self.nth_target
        if judge == 0:
            text.append("dame dane...")
        elif judge <= 25:
            text.append("?????????????????????")
        elif judge < 50:
            text.append("??????????????????????????????")
        elif judge < 70:
            text.append("???????????????????????????")
        elif judge < 120:
            text.append("???????????????????????????")
        elif judge < 200:
            line = "??????LP????????????????????????"
            if self.count[6] >= 8:
                line = "??????????????????......?????????" + line
            text.append(line)
        else:
            text.append("dame dane...")
        if self.tenjou:
            text.append("?????????????????????")
        return "\n".join(text)
        
    def summarize_tenpull(self, rst):
        team = [x["char"] for x in rst]
        pic = gen_team_pic(team)
        text = [f"{img_segment(pic)}"]
        text += [" ".join([f"???{x['star']}{x['char']}" for x in rst])]
        return "\n".join(text)    
        
if __name__ == "__main__":
    g = Gacha()
    g.set_banner("r6")
    pprint.pprint(g.banner)
    
