from __init__ import *

class Player:

    def __init__(self, name, rating, pos, stats, team, leag, country, ctype):
        self.name = name
        self.rating = rating
        self.pos = pos
        self.pac = stats[0]
        self.sho = stats[1]
        self.pas = stats[2]
        self.dri = stats[3]
        self.dff = stats[4]
        self.phy = stats[5]
        self.team = team
        self.leag = leag
        self.country = country
        self.ctype = ctype

    def to_dict(self):
        return {"name" : self.name, "rat" : self.rating, "pos" : self.pos, "pac" : self.pac, "sho" : self.sho,
                "pas" : self.pas, "dri" : self.dri, "dff" : self.dff, "phy" : self.phy, "tm" : self.team,
                "leag" : self.leag, "country" : self.country, "ctype" : self.ctype}

class Club:
    def __init__(self, source):
        self.df_club = pd.DataFrame.from_records(source["squad"])
        self.name = source["name"]

    def to_list(self, inp_page):
        if inp_page * 10 > self.df_club.shape[0]:
            page = math.ceil(self.df_club.shape[0] / 10)
        else:
            page = inp_page

        clb_page = self.df_club.sort_values(by="rat", ascending=False).iloc[((page - 1) * 10):(page * 10)].reset_index()
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
        plt.savefig('data_sg/temp_club.png')
        ax.clear()
