from __init__ import *

from textdistance import levenshtein
from PIL import Image, ImageDraw, ImageFont
import os.path

TEMP_CLUB = "data_sg/imgs/temp_club.png"
FINISHED_CARD = "data_sg/imgs/finished_card.png"
FINISHED_XI = "data_sg/imgs/finished_xi.png"
CARD_CLUB = "data_sg/imgs/card_club.png"
CARD_NAT = "data_sg/imgs/card_nat.png"
CARD_FACE = "data_sg/imgs/card_face.png"
FONT_TYPE = "data_sg/static/arial-unicode-ms.ttf"
FORM_MAPS = "data_sg/static/form_maps.json"
FORM_OFFSETS = "data_sg/static/form_offsets.json"

def claim():
    randnum = random.random()

    if randnum > 0.70:
        url = "https://www.futhead.com/ut/random/redirect/?type=bronze"
        color = "Bronze"
    elif randnum > 0.40:
        url = "https://www.futhead.com/ut/random/redirect/?type=silver"
        color = "Silver"
    elif randnum > 0.08:
        url = "https://www.futhead.com/ut/random/redirect/?type=gold"
        color = "Gold"
    else:
        url = "https://www.futhead.com/ut/random/redirect/?type=special"
        color = "Special"

    print(color)
    req = requests.get(url)
    soup = BeautifulSoup(req.content, "html.parser")

    name = soup.select_one("div.playercard-name").text.strip().title()
    rating = soup.select_one(".playercard-rating").text.strip()
    position = soup.select_one(".playercard-position").text.strip()

    info = soup.select("#info-tab > .font-12.margin-t-16 > .row.player-sidebar-item")
    info_tbl = {}
    chk = 0
    for row in info:
        info_dtype = row.select_one(".col-xs-7").text.strip()
        if info_dtype == "" and chk == 0:
            info_tbl["img_num"] = row.select_one(".col-xs-5.player-sidebar-value").text.strip()
            chk = 1
        elif info_dtype == "Club":
            info_tbl["clb_logo"] = row.img["src"].replace("https://futhead.cursecdn.com/static/img/22/clubs/","")
            info_tbl[info_dtype] = row.select_one(".col-xs-5.player-sidebar-value").text.strip()
        elif info_dtype == "Nation":
            info_tbl["nat_logo"] = row.img["src"].replace("https://futhead.cursecdn.com/static/img/22/nations/","")
            info_tbl[info_dtype] = row.select_one(".col-xs-5.player-sidebar-value").text.strip()
        else:
            info_tbl[info_dtype] = row.select_one(".col-xs-5.player-sidebar-value").text.strip()

    info_tbl["Age"] = info_tbl["Age"].split("-")[0].strip()
    info_tbl["Height"] = info_tbl["Height"].split("cm")[0].strip()

    stats = []
    for x in range(1, 7):
        stats.append(int(soup.select_one(".playercard-attr.playercard-attr" + str(x)).text.strip().split(" ")[0]))

    print(req.url)
    card_id = req.url.replace("https://www.futhead.com/22/players/", "").split("/")[0]

    return Player(name, rating, position, stats, color, card_id, info_tbl)

class Player:

    def __init__(self, name, rating, pos, stats, ctype, card_id, info_tbl, pd_row_or_dict=False):
        if pd_row_or_dict:
            self.card_id = name["card_id"]
            self.name = name["name"]
            self.rating = int(name["rat"])
            self.pos = name["pos"]
            self.pac = int(name["pac"])
            self.sho = int(name["sho"])
            self.pas = int(name["pas"])
            self.dri = int(name["dri"])
            self.dff = int(name["dff"])
            self.phy = int(name["phy"])
            self.ctype = name["ctype"]
            self.team = name["tm"]
            self.leag = name["leag"]
            self.country = name["country"]
            self.age = name["age"]
            self.height = name["height"]
            self.wkr = name["wkr"]
            self.nat_img = name["nat_img"]
            self.face_img = name["clb_img"]
            self.clb_img = name["face_img"]
        else:
            self.card_id = card_id
            self.name = name
            self.rating = int(rating)
            self.pos = pos
            self.pac = int(stats[0])
            self.sho = int(stats[1])
            self.pas = int(stats[2])
            self.dri = int(stats[3])
            self.dff = int(stats[4])
            self.phy = int(stats[5])
            self.ctype = ctype
            self.team = info_tbl["Club"]
            self.leag = info_tbl["League"]
            self.country = info_tbl["Nation"]
            self.age = info_tbl["Age"]
            self.height = info_tbl["Height"]
            self.wkr = info_tbl["Workrates"]
            self.nat_img = info_tbl["nat_logo"]
            self.face_img = info_tbl["img_num"]
            self.clb_img = info_tbl["clb_logo"]

    def unique_id(self):
        return "{}{}{}".format(self.name.replace(" ", ""), self.height, self.age)

    def to_dict(self):
        return {"card_id" : self.card_id, "name" : self.name, "rat" : self.rating, "pos" : self.pos, "pac" : self.pac, "sho" : self.sho,
                "pas" : self.pas, "dri" : self.dri, "dff" : self.dff, "phy" : self.phy, "tm" : self.team,
                "leag" : self.leag, "country" : self.country, "ctype" : self.ctype, "age" : self.age, "height" : self.height,
                "wkr" : self.wkr, "nat_img" : self.nat_img, "clb_img" : self.clb_img, "face_img" : self.face_img}

    def get_card(self):
        if os.path.isfile("data_sg/imgs/cards/{}.png".format(self.unique_id())):
            return "data_sg/imgs/cards/{}.png".format(self.unique_id())
        face_url = "https://futhead.cursecdn.com/static/img/22/players/{}.png".format(self.face_img)
        club_url = "https://futhead.cursecdn.com/static/img/22/clubs/{}".format(self.clb_img)
        nat_url = "https://futhead.cursecdn.com/static/img/22/nations/{}".format(self.nat_img)

        try:
            img_data = requests.get(face_url).content
            with open(CARD_FACE, 'wb') as handler:
                handler.write(img_data)
        except:
            img_data = requests.get("https://futhead.cursecdn.com/static/img/22/players_alt/p{}.png".format(self.face_img)).content
            with open(CARD_FACE, 'wb') as handler:
                handler.write(img_data)

        img_data = requests.get(club_url).content
        with open(CARD_CLUB, 'wb') as handler:
            handler.write(img_data)
        img_data = requests.get(nat_url).content
        with open(CARD_NAT, 'wb') as handler:
            handler.write(img_data)

        base = Image.open("data_sg/imgs/{}_card.png".format(self.ctype.lower())).convert("RGBA")
        face = Image.open(CARD_FACE, 'r').convert("RGBA")
        face = face.resize((round(face.size[0] * 4), round(face.size[1] * 4)))
        flag = Image.open(CARD_NAT, 'r').convert("RGBA")
        flag = flag.resize((round(flag.size[0] * 1.3), round(flag.size[1] * 1.3)))
        club = Image.open(CARD_CLUB, 'r').convert("RGBA")
        club = club.resize((round(club.size[0] * 1.3), round(club.size[1] * 1.3)))

        draw = ImageDraw.Draw(base)
        font = ImageFont.truetype(FONT_TYPE, size=90)
        rat_font = ImageFont.truetype(FONT_TYPE, size=190)
        if self.ctype == "Special":
            txt_fill = "rgb(255, 255, 255)"
        else:
            txt_fill = "rgb(0, 0, 0)"

        base.paste(face,(480, 300), face)

        ctr_line = 370
        w, h = draw.textsize(str(self.rating), rat_font)
        draw.text((ctr_line - (round(w/2)), 200), str(self.rating), fill=txt_fill, font=rat_font)
        w, h = draw.textsize(self.pos, font)
        draw.text((ctr_line - (round(w/2)), 420), self.pos, txt_fill, font=font)
        w, h = flag.size
        base.paste(flag,(ctr_line - (round(w/2)), 600), flag)
        w, h = club.size
        base.paste(club,(ctr_line - (round(w/2)), 700), club)

        draw.text((290, 1115), str(self.pac), fill=txt_fill, font=font)
        draw.text((290, 1230), str(self.sho), fill=txt_fill, font=font)
        draw.text((290, 1345), str(self.pas), fill=txt_fill, font=font)
        draw.text((745, 1115), str(self.dri), fill=txt_fill, font=font)
        draw.text((745, 1230), str(self.dff), fill=txt_fill, font=font)
        draw.text((745, 1345), str(self.phy), fill=txt_fill, font=font)

        mid_x, mid_y = base.size
        mid_x /= 2
        mid_y /= 2
        name_font_size = 110
        y_name = 950
        name_font = ImageFont.truetype(FONT_TYPE, size=name_font_size)
        name_w, name_h = draw.textsize(self.name, name_font)
        while name_w > 930:
            name_font = ImageFont.truetype(FONT_TYPE, size=name_font_size)
            name_w, name_h = draw.textsize(self.name, name_font)
            name_font_size -= 2
            y_name += 1
        draw.text((mid_x - (round(name_w / 2)), y_name), self.name, fill=txt_fill, font=name_font)

        base.save(FINISHED_CARD)
        base.save("data_sg/imgs/cards/{}.png".format(self.card_id))
        return FINISHED_CARD

class Club:
    def __init__(self, source=None, new=None):
        if new == None:
            self.df_club = pd.DataFrame.from_records(source["squad"])
            self.name = source["name"]
        else:
            self.name = new[0]
            self.df_club = [new[1].to_dict()]

    def search(self, player):
        self.df_club["norm name"] = self.df_club['name'].str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        self.df_club["levdist"] = self.df_club.apply(lambda x: levenshtein.distance(x['norm name'].lower(),  player.lower()), axis=1)
        df_dist = self.df_club[self.df_club["levdist"] < 2].sort_values(by="levdist").reset_index()
        print(df_dist)
        return df_dist

    def to_dict(self):
        return {"name" : self.name, "squad" : self.df_club}

    def to_list(self, inp_page):
        if inp_page * 10 > self.df_club.shape[0]:
            page = math.ceil(self.df_club.shape[0] / 10)
        else:
            page = inp_page

        clb_page = self.df_club.sort_values(by="rat", ascending=False).reset_index().iloc[((page - 1) * 10):(page * 10)]
        clb_page["stats"] = clb_page["pac"] + clb_page["sho"] +  clb_page["pas"] + clb_page["dri"] + clb_page["dff"] + clb_page["phy"]
        clb_page = clb_page[["name", "pos", "rat", "stats", "country", "leag"]]
        clb_page.columns = ["Name", " Pos ", "Rating", "Stats", "Country", "League"]

        ax = plt.subplot(911, frame_on=False)  # no visible frame
        ax.xaxis.set_visible(False)  # hide the x axis
        ax.yaxis.set_visible(False)  # hide the y axis
        tbl = table(ax, clb_page)  # where df is your data frame
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(10)
        tbl.auto_set_column_width(col=list(range(clb_page.shape[1])))
        plt.savefig(TEMP_CLUB)
        ax.clear()

class XI:

    def __init__(self, form="442", source=None):
        if source == None:
            self.xi = {}
            for x in range(1,12):
                self.xi[str(x)] = {"pos" : "", "plr" : ""}
            self.form = "442"
            self.map_positions()
        else:
            self.xi = source["xi"]
            self.form = source["form"]

    def map_positions(self):
        self.xi["1"]["pos"] = "GK"

        with open(FORM_MAPS, 'r', encoding='utf-8') as f:
            maps = json.load(f)

        for i in range(2,12):
            self.xi[str(i)]["pos"] = maps[self.form][str(i)]

    def to_img(self):
        with open(FORM_MAPS, 'r', encoding='utf-8') as f:
            maps = json.load(f)[self.form]
        with open(FORM_OFFSETS, 'r', encoding='utf-8') as f:
            offsets = json.load(f)[self.form]

        base = Image.open("data_sg/imgs/xi_bg.png").convert("RGBA")
        base = base.resize((1200, 1200))
        na_card = Image.open("data_sg/imgs/no_card.png").convert("RGBA")
        na_card = na_card.resize((round(na_card.size[0] * 0.34), round(na_card.size[1] * 0.3)))
        na_w, na_l = na_card.size
        for i in range(1,12):
            if self.xi[str(i)]["plr"] == "":
                base.paste(na_card, (round(offsets[str(i)][0] - (na_w / 2)),
                                     round(offsets[str(i)][1] - (na_l / 2))), na_card)
            else:
                tmp_card = Image.open("data_sg/imgs/cards/{}.png".format(self.xi[str(i)]["plr"]["card_id"]))
                tmp_card = tmp_card.resize((round(tmp_card.size[0] * 0.19), round(tmp_card.size[1] * 0.17)))
                tmp_w, tmp_l = tmp_card.size
                base.paste(tmp_card, (round(offsets[str(i)][0] - (tmp_w / 2)),
                                      round(offsets[str(i)][1] - (tmp_l / 2))), tmp_card)
        base.save(FINISHED_XI)
        return FINISHED_XI

    def to_dict(self):
        return {"form" : self.form, "xi" : self.xi}

if __name__ == "__main__":
    test_plr = claim()
    test_plr.get_card()