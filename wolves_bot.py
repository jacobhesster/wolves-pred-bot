from __init__ import *

from discord.ext import commands
import discord
from numpy import nan
import datetime as dt
import plotly.graph_objects as go
import tweepy
from wol_bot_static import token, teams, ha, pred_cols, twitter_apikey, twitter_secret_apikey, \
    twitter_access_token, twitter_secret_access_token, poll_channel, help_brief, help_desc
import asyncio
from random import randrange
from SG2 import Player, Club, XI, claim, TEMP_CLUB

# token - Discord bot token
# teams - dictionary for converting team code to full team name
# ha    - dictionary for converting h to home and a to away
# pred_ - columns for prediction data

# prediction league functions
def game_result(wolves, opp):
    if(wolves > opp):
        return "wolves"
    elif(opp > wolves):
        return "opp"
    else:
        return "draw"

def make_ordinal(n):
    '''
    Convert an integer into its ordinal representation::

        make_ordinal(0)   => '0th'
        make_ordinal(3)   => '3rd'
        make_ordinal(122) => '122nd'
        make_ordinal(213) => '213th'
    '''
    n = int(n)
    suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    return str(n) + suffix

def refresh_scores():
    pred = pd.read_csv('data_wol/predictions.csv')
    results = pd.read_csv('data_wol/results.csv')

    #get games that need their point values to be updated
    update = pred[pred['pts'].isnull()]

    for index, row in update.iterrows():
        game = results[(results['game'] == row['game']) & (results['opp_score'].notnull())]

        #if game has been played and has a result, add the points, otherwise pass
        if game.shape[0] > 0:
            total_pts = 0
            ind = min(list(game.index))
            if (game['opp_score'][ind] == row['opp_score']):
                total_pts += 1

            if (game['wolves'][ind] == row['wolves']):
                total_pts += 1

            if (game_result(game['wolves'][ind], game['opp_score'][ind]) == game_result(row['wolves'], row['opp_score'])):
                total_pts += 2

            pred.at[index, 'pts'] = int(total_pts)

    pred.to_csv('data_wol/predictions.csv', index=False)

# poll functions
def get_poll_info(polls, code):
    return polls[polls["code"] == code.lower()]

def get_user_responses(responses, code, author):
    return responses[(responses["user"] == str(author)) & (responses["code"] == code)]

def get_poll_results(responses, polls, code):
    poll = get_poll_info(polls, code)
    poll_responses = responses[responses["code"] == code]["response"].value_counts(normalize=True)
    msg = "Results:\n**{}**\n```".format(poll["poll"].iloc[0])
    other = 0
    for i in range(len(poll_responses)):
        if i <= 4:
            msg += "{:18.15}  {:.1f}%\n".format(poll_responses.index[i], poll_responses[i] * 100)
        else:
            other += poll_responses[i]
    if other > 0:
        msg += "{:18.15}  {:.1f}%```".format("other", other * 100)
    else:
        msg += "```"
    return msg

def add_polls_row(polls, code, poll, limit):
    nr = pd.DataFrame({"code": code, "poll": poll, "vote_limit": limit, "open": 1}, index=[0])
    pd.concat([nr, polls]).reset_index(drop=True).to_csv('data_wol/polls.csv', index=False)

def add_responses_row(responses, code, response, author):
    nr = pd.DataFrame({"code": code, "response": response, "user": author}, index=[0])
    pd.concat([nr, responses]).reset_index(drop=True).to_csv("data_wol/poll_responses.csv", index=False)

def poll_code_exists(polls, code):
    return code in polls['code'].unique()

def clean_mentions_str(mention):
    return mention.replace("<", "").replace(">", "").replace("@", "").replace("!", "")

async def make_sg_table(df_table):
    df_table["ppg"] = df_table["pts"] / (df_table["w"] + df_table["l"] + df_table["d"])
    df_table["ppg"] = [round(x, 2) for x in df_table["ppg"]]
    df_table.sort_values(by=["elo", "ppg", "gd"], ascending=(False, False, False), inplace=True)
    df_table["rank"] = range(1, len(df_table) + 1)
    df_table.set_index("rank", inplace=True)
    df_table.columns = ["User", "Wins", "Losses", "Draws", "  GF  ", "  GA  ", "  GD  ", "  Pts  ", "  ELO  ", "  PPG  "]
    df_table[["Wins", "Losses", "Draws", "  GF  ", "  GA  ", "  GD  ", "  Pts  ", "  ELO  "]] = df_table[["Wins", "Losses", "Draws", "  GF  ", "  GA  ", "  GD  ", "  Pts  ", "  ELO  "]].astype(int)
    df_table["User"] = [await bot.fetch_user(int(id)) for id in df_table["User"]]
    df_table["User"] = [id.name for id in df_table["User"]]
    ax = plt.subplot(911, frame_on=False)  # no visible frame
    ax.xaxis.set_visible(False)  # hide the x axis
    ax.yaxis.set_visible(False)  # hide the y axis
    tbl = table(ax, df_table)  # where df is your data frame
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.auto_set_column_width(col=list(range(df_table.shape[1])))
    plt.savefig('data_wol/sg_table.png')
    ax.clear()

def update_sg_table(df_table, user, res, gf, ga, pts, sort=False):
    # TODO: Add ELO ratings
    if user in df_table["user"].values:
        print("user found")
        row = df_table[df_table["user"] == user].iloc[0]
        row.update(pd.Series([
            row[res] + 1,
            row["gf"] + gf,
            row["ga"] + ga,
            row["pts"] + pts
        ], index=[res, "gf", "ga", "pts"]))
        df_table.loc[row.name] = row
    else:
        print("user not found")
        temp = pd.Series([len(df_table) + 1, str(user), 0, 0, 0, 0, 0, 0, 0, 1500], index=df_table.columns)
        df_table = df_table.append(temp, ignore_index=True)
        row = df_table[df_table["user"] == user].iloc[0]
        row.update(pd.Series([
            row[res] + 1,
            row["gf"] + gf,
            row["ga"] + ga,
            row["pts"] + pts
        ], index=[res, "gf", "ga", "pts"]))
        df_table.loc[row.name] = row

    if sort:
        df_table["gd"] = df_table["gf"] - df_table["ga"]
        df_table["ppg"] = df_table["pts"] / (df_table["w"] + df_table["d"] + df_table["l"])
        df_table.sort_values(by=["elo", "ppg", "gd"], ascending=False, inplace=True)
        df_table.drop("ppg", axis=1, inplace=True)
        df_table["rank"] = range(1, len(df_table) + 1)

    return df_table

def check_if_open(user1, user2):
    try:
        with open('data_wol/sg_open.json', 'r', encoding='utf-8') as f:
            comp_open = json.load(f)
        return comp_open[user1] == "open" and comp_open[user2] == "open"
    except:
        return False

def update_elo(df_table, user1, user2, result):
    if result == ("w", "l"):
        res = (1, 0)
    elif result == ("l", "w"):
        res = (0, 1)
    else:
        res = (0.5, 0.5)
    row1 = df_table[df_table["user"] == user1].iloc[0]
    row2 = df_table[df_table["user"] == user2].iloc[0]
    elo1 = int(row1["elo"])
    elo2 = int(row2["elo"])
    t1_trans = 10 ** (elo1 / 400)
    t2_trans = 10 ** (elo2 / 400)
    t1_exp = t1_trans / (t1_trans + t2_trans)
    t2_exp = t2_trans / (t1_trans + t2_trans)
    expected = (t1_exp, t2_exp)
    K = 16
    row1["elo"] = int(elo1 + K * (res[0] - expected[0]))
    row2["elo"] = int(elo2 + K * (res[1] - expected[1]))
    df_table.loc[row1.name] = row1
    df_table.loc[row2.name] = row2
    return df_table

#refresh scores on startup
refresh_scores()

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(intents=intents, command_prefix='$')

sg_table_loc = "data_wol/sg_table_bronze.csv"

@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))

@bot.command(brief=help_brief["ping"], description=help_desc["ping"])
async def ping(ctx):
    latency = bot.latency
    await ctx.send(latency)

# prediction table commands

@bot.command(brief=help_brief["score"], description=help_desc["score"])
async def score(ctx, game, score):
    results_score = pd.read_csv('data_wol/results.csv')
    pred_score = pd.read_csv('data_wol/predictions.csv')

    #get data
    author = str(ctx.message.author)
    score_parts = score.split('-') #command will have wolves score first and opp score second

    #check if game exists
    exists_v = results_score['game'].str.contains(game)
    exists = (exists_v.sum()) > 0

    if exists:
        date = results_score[results_score['game'] == game]['date']
        time = results_score[results_score['game'] == game]['time']
        fixture = dt.datetime.strptime('{} {}'.format(date[min(date.index)], time[min(time.index)]), '%m/%d/%Y %H:%M')

        #if (fixture < dt.datetime.now()):
        #    message = "It's too late to predict {} {}.".format(teams[game[0:2]], ha[game[2]])
        #else:

        nrow = [author, game, score_parts[1], score_parts[0], nan]  # data has opp first, wolves second

        #overwrite if exists
        overwrite_check = pred_score[(pred_score['user'] == author) & (pred_score['game'] == game)]
        if overwrite_check.shape[0] == 1:
            pred_score.loc[list(overwrite_check.index)[0]] = nrow
        else:
            pred_score = pred_score.append(pd.DataFrame([nrow], columns=pred_cols), ignore_index=True)

        pred_score.to_csv('data_wol/predictions.csv', index=False)
        message = "Score recorded! You predicted Wolves {}, {} {}.".format(score_parts[0], teams[game[:-1]], score_parts[1])
    else:
        nexts = results_score[results_score['wolves'].isnull()]['game']
        next = nexts[min(nexts.index)]
        message = "Please enter prediction for the next match {} {} with game code '{}'.".format(teams[next[0:2]], ha[next[2]], next)

    await ctx.send(message)

@bot.command(brief=help_brief["format"], description=help_desc["format"])
async def format(ctx):
    results_format = pd.read_csv('data_wol/results.csv')
    nexts = results_format[results_format['wolves'].isnull()]['game']
    next = nexts[min(nexts.index)]
    message = "Command should be formatted as '$score GAMECODE WOLSCORE-OPPSCORE'. Example, '$score mch 2-1' where 'mch' " \
              "translates to 'Manchester City Home'. Next match is {} {} with a game code of '{}'.\n\nScoring is as follows:"\
              "\n2 pts for the correct result\n1 pt for each correct goal total.".format(teams[next[0:2]], ha[next[2]], next)
    await ctx.message.author.send(message)

@bot.command(hidden=True)
async def short_lb(ctx):
    pred_lb = pd.read_csv('data_wol/predictions.csv')
    lb = pred_lb.groupby(['user']).sum().sort_values(by=['pts'], ascending=False).reset_index()
    top_5 = lb.nlargest(5, 'pts')
    user = lb[lb['user'] == str(ctx.author)]
    message = '```  Rank  |       User       |  Pts  \n'
    for index, row in top_5.iterrows():
        message += '{:^8}|{:^18}|{:^7}\n'.format(make_ordinal(index + 1), row['user'].split('#')[0], int(row['pts']))
    message += '...\n{:^8}|{:^18}|{:^7}```'.format(make_ordinal(list(user.index)[0] + 1), list(user['user'])[0].split('#')[0],
                                              int(list(user['pts'])[0]))
    await ctx.send(message)

@bot.command(hidden=True)
async def leaderboard(ctx):
    full_pred_lb = pd.read_csv('data_wol/predictions.csv')
    full_lb = full_pred_lb.groupby(['user']).sum().sort_values(by=['pts'], ascending=False).reset_index()
    user_list = [x.split('#')[0] for x in list(full_lb['user'])]

    files = []

    for i in range(math.ceil(len(user_list) / 20)):
        if i * 20 < len(user_list):
            temp_full_lb = full_lb[(i * 20):((i + 1) * 20)]
            temp_user_list = user_list[(i * 20):((i + 1) * 20)]
        else:
            temp_full_lb = full_lb[(i * 20):len(full_lb)]
            temp_user_list = user_list[(i * 20):len(user_list)]
        layout = go.Layout(autosize=True, margin = {'l': 0, 'r': 0, 't': 0, 'b': 0} )
        fig = go.Figure(layout=layout, data=[go.Table(columnwidth=[10, 15, 10],
                                       header=dict(values=['Rank', 'User', 'Points'], font=dict(color='black', size=12),
                                                   height=(500 / (temp_full_lb.shape[0] + 1))),
                                       cells=dict(
                                           values=[list(range((i * 20) + 1, ((i + 1) * 20) + 1)), temp_user_list, list(temp_full_lb['pts'])],
                                           font=dict(color='black', size=11), height= (500 / (temp_full_lb.shape[0] + 1))))
                              ])
        fig.update_layout(width=350, height=700) #(25 * (full_lb.shape[0] + 2))
        fig.write_image("data_wol/table{}.png".format(i))
        files.append("data_wol/table{}.png".format(i))

    await asyncio.wait([ctx.send(file=discord.File(f)) for f in files])

@bot.command(hidden=True)
async def refresh(ctx):
    refresh_scores()
    await ctx.send('Scores have been updated.')

# fa cup

@bot.command()
async def confirm_fa(ctx):
    confirms = pd.read_csv("data_wol/fa_confirmed.csv")
    if ctx.author.id in set(confirms["id"]):
        await ctx.send('You are already registered.')
    else:
        confirms = confirms.append(pd.DataFrame([[ctx.author.id, "confirmed"]], columns=["id","confirmed"]), ignore_index=True)
        confirms.to_csv("data_wol/fa_confirmed.csv", index=False)
        await ctx.send('You are confirmed for the upcoming Wolves Prediction FA Cup.')

@bot.command(hidden=True, pass_context=True)
async def nextround(ctx):
    matchups = pd.read_csv("data_wol/matchups.csv")
    comp = json.load(open('data_wol/comp.json'))
    confirms = pd.read_csv("data_wol/fa_confirmed.csv")
    confirms_list = list(set(confirms["id"]))

    if comp["tot"] == comp["done"]:
        champ = list(set(matchups[matchups["round"] == comp["done"]]["winner"]))[0]
        user = bot.get_user(int(champ))
        print("Tourney is over! Congrats {}".format(user))

    elif comp["name"] == "none":

        # start comp
        #
        # is this a general formula? no because confirms go away after qualifier

        all_mems = [member.id for member in ctx.guild.members]
        tot_mems = len(all_mems)

        comp["name"] = "facup"
        comp["tot"] = math.ceil(math.log(tot_mems,2))
        comp["quals"] = comp["tot"] - 7 if comp["tot"] > 7 else 0
        comp["done"] = 1
        comp["status"] = "open"

        rd = comp["done"]
        bye = ((2 ** (comp["tot"] - rd)) * 2) - tot_mems
        print(bye)

        while bye > 0:
            if len(confirms_list) > 0:
                conf_bye = confirms_list.pop(randrange(len(confirms_list)))
                all_mems.remove(conf_bye)
                matchups = matchups.append(pd.DataFrame([[rd, conf_bye, -1, "", "bye", conf_bye]],
                                              columns=list(matchups.columns)), ignore_index=True)
            else:
                reg_bye = all_mems.pop(randrange(len(all_mems)))
                matchups = matchups.append(pd.DataFrame([[rd, reg_bye, -1, "", "bye", reg_bye]],
                                                        columns=list(matchups.columns)), ignore_index=True)
            bye -= 1

        while len(all_mems) > 1:
            home = all_mems.pop(randrange(len(all_mems)))
            away = all_mems.pop(randrange(len(all_mems)))
            matchups = matchups.append(pd.DataFrame([[rd, home, away, "", "", ""]],
                                                    columns=list(matchups.columns)), ignore_index=True)

        if len(all_mems) > 0:
            reg_bye = all_mems.pop(randrange(len(all_mems)))
            matchups = matchups.append(pd.DataFrame([[rd, reg_bye, -1, "", "bye", reg_bye]],
                                                    columns=list(matchups.columns)), ignore_index=True)

        print(matchups[matchups["round"] == 1].shape[0])
        matchups.to_csv("data_wol/matchups.csv", index=False)
        with open('data_wol/comp.json', 'w', encoding='utf-8') as f:
            json.dump(comp, f, ensure_ascii=False, indent=4)
        #pd.DataFrame(columns=["id","confirmed"]).to_csv("data_wol/fa_confirmed.csv", index=False)

    else:
        print("match-ups for round > 1")
        matchups = pd.read_csv("data_wol/matchups.csv")
        comp = json.load(open('data_wol/comp.json'))
        qual = comp["quals"] < comp["done"]
        confirms_list = []
        if qual:
            confirms = pd.read_csv("data_wol/fa_confirmed.csv")
            confirms_list = list(set(confirms["id"]))
        winners = list(set(matchups[matchups["round"] == comp["done"]]["winner"]))
        comp["done"] += 1
        rd = comp["done"]
        bye = ((2 ** (comp["tot"] - rd)) * 2) - len(winners)

        while bye > 0:
            if len(confirms_list) > 0:
                conf_bye = confirms_list.pop(randrange(len(confirms_list)))
                winners.remove(conf_bye)
                matchups = matchups.append(pd.DataFrame([[rd, conf_bye, -1, "", "bye", conf_bye]],
                                              columns=list(matchups.columns)), ignore_index=True)
            else:
                reg_bye = winners.pop(randrange(len(winners)))
                matchups = matchups.append(pd.DataFrame([[rd, reg_bye, -1, "", "bye", reg_bye]],
                                                        columns=list(matchups.columns)), ignore_index=True)
            bye -= 1

        while len(winners) > 1:
            home = winners.pop(randrange(len(winners)))
            away = winners.pop(randrange(len(winners)))
            matchups = matchups.append(pd.DataFrame([[rd, home, away, "", "", ""]],
                                                    columns=list(matchups.columns)), ignore_index=True)

        if len(winners) > 0:
            reg_bye = winners.pop(randrange(len(winners)))
            matchups = matchups.append(pd.DataFrame([[rd, reg_bye, -1, "", "bye", reg_bye]],
                                                    columns=list(matchups.columns)), ignore_index=True)

        print(matchups[matchups["round"] == comp["done"]].shape[0])
        matchups.to_csv("data_wol/matchups.csv", index=False)
        with open('data_wol/comp.json', 'w', encoding='utf-8') as f:
            json.dump(comp, f, ensure_ascii=False, indent=4)
        #pd.DataFrame(columns=["id","confirmed"]).to_csv("data_wol/fa_confirmed.csv", index=False)

@bot.command(hidden=True, pass_context=True)
async def simulate(ctx):
    matchups = pd.read_csv("data_wol/matchups.csv")
    comp = json.load(open('data_wol/comp.json'))
    if comp["done"] == comp["quals"]:
        confirms = pd.read_csv("data_wol/fa_confirmed.csv")
        confirms_list = list(set(confirms["id"]))
    winners = []

    for index, row in matchups.iterrows():
        if row["a_pred"] == "bye":
            winners.append(row["winner"])
        elif row["winner"] > 100:
            winners.append(row["winner"])
        else:
            if randrange(2) == 0:
                #######
                ##
                ##   HOW DO I GET A USER NAME FROM THE USER ID???
                ##
                ########
                print(await bot.fetch_user(row["home"]))
                winners.append(row["home"])
            else:
                winners.append(row["away"])

    matchups["winner"] = winners
    matchups.to_csv("data_wol/matchups.csv", index=False)

# tweet commands

@bot.command(hidden=True)
async def tweet(ctx, *, tweet):
    auth = tweepy.OAuthHandler(twitter_apikey, twitter_secret_apikey)
    auth.set_access_token(twitter_access_token, twitter_secret_access_token)
    api = tweepy.API(auth)
    api.update_status(tweet)
    await ctx.send('You tried to Tweet: {}'.format(tweet))

@bot.command(brief=help_brief["tweethelp"], description=help_desc["tweethelp"])
async def tweethelp(ctx):
    await ctx.send("Jeff Shi can tweet! Any message with three 💬 reactions will be tweeted to the Discord Twitter account "
                   "(as long as mods permit). Messages with the 🔹 reaction have been sent. Check out the server Twitter page "
                   "at https://twitter.com/WwfcDiscord")

@bot.event
async def on_reaction_add(reaction, user):
    print(reaction.message.content)
    print(reaction.emoji)
    channel_id = 346329500637855745
    #channel_id = 557526209043628032
    if reaction.message.channel.id != channel_id:
        return

    if reaction.emoji == "💬":
        reaction_ct = reaction.message.reactions
        tweet_go = 0
        already_tweeted = 0
        mod_denied = 0
        print(reaction_ct)
        for re in reaction_ct:
            if re.emoji == "📵" and re.count > 0:
                mod_denied = 1
            if re.emoji == "🔹" and re.count > 0 and re.me:
                already_tweeted = 1
            if re.emoji == "💬" and re.count >= 3:
                tweet_go = 1
                print("tweet is a go")

            if already_tweeted > 0:
                print("already tweeted")
                return
            elif mod_denied > 0:
                print("the mod denied your tweet")
                return
            elif tweet_go > 0:
                auth = tweepy.OAuthHandler(twitter_apikey, twitter_secret_apikey)
                auth.set_access_token(twitter_access_token, twitter_secret_access_token)
                api = tweepy.API(auth)
                api.update_status(reaction.message.content)
                print("sent tweet")
                await reaction.message.add_reaction("🔹")
    return
    #await reaction.message.channel.send(reaction.emoji)

## SG stuff
#with open('data_wol/comp.json', 'w', encoding='utf-8') as f:
 #   json.dump(comp, f, ensure_ascii=False, indent=4)

  #  comp = json.load(open('data_wol/comp.json'))
@bot.command()
async def sg_comp(ctx, op):
    if op.lower() in ['open', 'closed']:
        with open('data_wol/sg_open.json', 'r', encoding='utf-8') as f:
            comp_open = json.load(f)
        comp_open[str(ctx.author.id)] = op
        with open('data_wol/sg_open.json', 'w', encoding='utf-8') as f:
            json.dump(comp_open, f, ensure_ascii=False, indent=4)
        await ctx.send("<@{}> is now {} for league matches.".format(ctx.author.id, op))
    elif op.lower() == 'help':
        await ctx.send("Use this command to tell Jeff if you want your matches to count towards the official table.")
    else:
        await ctx.send("<@{}> Not valid. Please use 'open' or 'closed' to indicate whether you are open for ranked matches or not. Use 'help' for info.".format(ctx.author.id))

@bot.command()
async def sg_open(ctx):
    with open('data_wol/sg_open.json', 'r', encoding='utf-8') as f:
        comp_open = json.load(f)
    open_table = ""
    for key in comp_open.keys():
        open_table += "| {} |  {}\n".format(comp_open[key].replace("open", "  OPEN  ").upper(), await bot.fetch_user(int(key)))
    await ctx.send(open_table)

@bot.command()
async def sg_table(ctx):
    df_table = pd.read_csv(sg_table_loc, dtype={'user': 'str'})
    await make_sg_table(df_table)
    await asyncio.wait([ctx.send(file=discord.File("data_wol/sg_table.png"))])

@bot.event
async def on_message_edit(message_before, message_after):

    if len(message_after.embeds) > 0 and message_after.channel.id in [914630952414761092, 915742189424898120]:
        emb = message_after.embeds[0]

        if emb.description.split("\n")[2] == 'Status - ***Full-time***':
            score = emb.description.split("\n")[0]
            spl_score = score.split('`')
            home = spl_score[2].replace("*","").strip()
            away = spl_score[4].replace("*","").strip()
            hscore = int(spl_score[3].split("-")[0])
            ascore = int(spl_score[3].split("-")[1])

            df_table = pd.read_csv(sg_table_loc, dtype={'user': 'str'})

            hmgr = clean_mentions_str(emb.fields[0].value.split("\n\n")[0].replace("Manager: ", ""))
            amgr = clean_mentions_str(emb.fields[1].value.split("\n\n")[0].replace("Manager: ", ""))

            if hscore > ascore:
                pts = (3,0)
                res = ("w", "l")
            elif hscore < ascore:
                pts = (0,3)
                res = ("l", "w")
            else:
                pts = (1,1)
                res = ("d", "d")
            if check_if_open(hmgr, amgr):
                df_table = update_sg_table(df_table, hmgr, res[0], hscore, ascore, pts[0])
                df_table = update_sg_table(df_table, amgr, res[1], ascore, hscore, pts[1], sort=True)
                df_table = update_elo(df_table, hmgr, amgr, res)
                df_table.to_csv(sg_table_loc, index=False)
                await message_after.channel.send("Result counted towards table.\n{}: {}\n{}: {}".format(home, hscore, away, ascore))
            else:
                await message_after.channel.send("Result does not count. One or more teams are closed for competitive matches.")
# poll commands

@bot.command(hidden=True)
async def addpoll(ctx, code, limit, *poll_args):
    poll = ' '.join(poll_args)
    code = code.lower()
    polls = pd.read_csv('data_wol/polls.csv')

    if poll_code_exists(polls, code):
        msg = "Code '{}' already exists. Try a new code.".format(code)
    else:
        add_polls_row(polls, code, poll, limit)
        await bot.get_channel(poll_channel).send("New poll added:\n**{}**\n"
                                                 "Code: **{}**\nResponse limit: **{}**\n"
                                                 "Respond in #poll-spam with command '$vote {} *RESPONSE*'".format(poll, code, limit, code))
        msg = "Poll added with code {}. Response limited to {} per user.".format(code, limit)
    await ctx.send(msg)

@bot.command(hidden=True)
async def closepoll(ctx, code, delete):
    code = code.lower()
    delete = delete.lower()
    polls = pd.read_csv('data_wol/polls.csv')
    responses = pd.read_csv("data_wol/poll_responses.csv")

    if delete.lower() == "del":
        polls[polls['code'] != code].to_csv('data_wol/polls.csv', index=False)
        responses[responses['code'] != code].to_csv("data_wol/poll_responses.csv", index=False)
        msg = "Poll with code {} removed.".format(code)

    elif delete.lower() == "clo":
        pl_ind = polls.index[polls["code"] == code.lower()].tolist()
        if len(pl_ind) > 0:
            polls.at[pl_ind[0], "open"] = 0
            polls.to_csv('data_wol/polls.csv', index=False)
            close_msg = "Poll closed:\nCode: **{}**".format(code)
            results_msg = get_poll_results(responses, polls, code)
            await bot.get_channel(poll_channel).send(close_msg)
            await bot.get_channel(poll_channel).send(results_msg)
            msg = "Poll with code {} closed.".format(code)
        else:
            msg = "Poll with code {} does not exist.".format(code)
    else:
        msg = "Wrong code. Please use 'del' to delete poll or 'clo' to close poll."
    await ctx.send(msg)

@bot.command(brief=help_brief["openpolls"], description=help_desc["openpolls"])
async def openpolls(ctx):
    polls = pd.read_csv('data_wol/polls.csv')

    open_polls = polls[polls["open"] == 1]
    if open_polls.shape[0] == 0:
        msg = "No open polls."
    else:
        msg = ""
        for index, row in open_polls.iterrows():
            msg += "Poll:**{}**\nCode: **{}**  Vote Limit: **{}**\n\n".format(row["poll"],row["code"], row["vote_limit"])
    await ctx.send(msg.strip())

@bot.command(brief=help_brief["vote"], description=help_desc["vote"])
async def vote(ctx, code, *full_response):
    response = ' '.join(full_response)
    code = code.lower()
    polls = pd.read_csv('data_wol/polls.csv')
    responses = pd.read_csv("data_wol/poll_responses.csv")

    poll_limit = get_poll_info(polls, code)["vote_limit"].to_list()
    if len(poll_limit) > 0:
        prev_response = get_user_responses(responses, code, ctx.author)
        if prev_response.shape[0] >= poll_limit[0]:
            msg = "You already voted {} time(s). Your vote(s):\n".format(prev_response.shape[0])
            for resp in prev_response["response"].to_list():
                msg += resp + ", "
            msg = msg[:-2] + "\nTo change vote, use command '$cvote *CODE* *NEW_RESPONSE*'."
        else:
            add_responses_row(responses, code, response, ctx.author)
            msg = "You voted for {}.".format(response)
    else:
        msg = "Code {} does not exist. Try *$openpolls* to check open polls.".format(code)

    await ctx.send(msg)

@bot.command(brief=help_brief["getvote"], description=help_desc["getvote"])
async def getvote(ctx, code):
    code = code.lower()
    responses = pd.read_csv("data_wol/poll_responses.csv")

    prev_response = get_user_responses(responses, code, ctx.author)
    msg = "Your vote(s):\n"
    for resp in prev_response["response"].to_list():
        msg += resp + ", "

    await ctx.send(msg[:-2] + "\nTo change vote, use command '$cvote *CODE* *RESPONSE*'.")

@bot.command(brief=help_brief["cvote"], description=help_desc["cvote"])
async def cvote(ctx, code, *new_response):
    response = ' '.join(new_response)
    code = code.lower()
    responses = pd.read_csv("data_wol/poll_responses.csv")
    polls = pd.read_csv("data_wol/polls.csv")

    prev_response = get_user_responses(responses, code, ctx.author)
    if prev_response.shape[0] == 0:
        msg = "You have not voted for this poll yet or poll {} does not exist.".format(code)
    else:
        pr = prev_response.iloc[-1]["response"]
        nr = pd.DataFrame({"code": code, "response": response, "user": ctx.author}, index=[0])
        pd.concat([nr, responses.drop(prev_response.iloc[-1].name)]).reset_index(drop=True).to_csv("data_wol/poll_responses.csv", index=False)
        msg = "You replaced '{}' with '{}'.".format(pr, response)

    await ctx.send(msg)

@bot.command(hidden=True)
async def results(ctx, code):
    code = code.lower()
    responses = pd.read_csv("data_wol/poll_responses.csv")
    polls = pd.read_csv("data_wol/polls.csv")

    if poll_code_exists(polls, code):

        msg = get_poll_results(responses, polls, code)
    else:
        msg = "Poll with code {} does not exist.".format(code)

    await ctx.send(msg)

#### SOCCER GURU???? ####

@bot.command(hidden=True)
@commands.cooldown(1, 60, commands.BucketType.user)
async def sg_claim(ctx):
    new_plr = claim()
    new_plr_card = new_plr.get_card()

    try:
        with open('data_sg/clubs/{}.json'.format(str(ctx.author.id)), 'r', encoding='utf-8') as f:
            ex_clb = json.load(f)

        ex_clb["squad"].append(new_plr.to_dict())

        with open('data_sg/clubs/{}.json'.format(str(ctx.author.id)), 'w', encoding='utf-8') as f:
            json.dump(ex_clb, f, ensure_ascii=False, indent=4)
    except:
        new_clb = Club(new=(str(ctx.author.id),new_plr)).to_dict()
        new_xi = XI().to_dict()

        with open('data_sg/clubs/{}.json'.format(str(ctx.author.id)), 'w', encoding='utf-8') as f:
            json.dump(new_clb, f, ensure_ascii=False, indent=4)
        with open('data_sg/xis/{}.json'.format(str(ctx.author.id)), 'w', encoding='utf-8') as f:
            json.dump(new_xi, f, ensure_ascii=False, indent=4)

    await ctx.send("{} ({}) joins your club!".format(new_plr.name, new_plr.ctype))
    await asyncio.wait([ctx.send(file=discord.File(new_plr_card))])

@bot.command(hidden=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def sg_club(ctx, page: int):
    try:
        with open('data_sg/clubs/{}.json'.format(str(ctx.author.id)), 'r', encoding='utf-8') as f:
            ex_clb = Club(json.load(f))
            ex_clb.to_list(page)
            await asyncio.wait([ctx.send(file=discord.File(TEMP_CLUB))])
    except Exception as e:
        print(e)
        await ctx.send("<@{}> Your club does not exist! Type '$sg_claim' to get a player.".format(ctx.author.id))

@bot.command(hidden=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def sg_show(ctx, *player: str):
    try:
        with open('data_sg/clubs/{}.json'.format(str(ctx.author.id)), 'r', encoding='utf-8') as f:
            ex_clb = Club(json.load(f))

        df_dist = ex_clb.search(" ".join(player))

        if df_dist.shape[0] > 0:
            match = df_dist.loc[0]
            await ctx.send("```{} ({})  Rating: {}\nPosition: {}\nNation: {}\nTeam: {}\nLeague: {}\n\n" \
            "PAC: {}     DRI: {}\nSHO: {}     DEF: {}\nPAS: {}     PHY: {}```".format(match["name"], match["ctype"],
                                match["rat"], match["pos"], match["country"], match["tm"], match["leag"],
                                match["pac"], match["dri"], match["sho"], match["dff"], match["pas"], match["phy"]))
        else:
            await ctx.send("No match for {}".format(player))

    except Exception as e:
        print(e)
        await ctx.send("<@{}> Your club does not exist! Type '$sg_claim' to get a player.".format(ctx.author.id))

@bot.command(hidden=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def sg_add(ctx, *player: str):
    try:
        with open('data_sg/clubs/{}.json'.format(str(ctx.author.id)), 'r', encoding='utf-8') as f:
            ex_clb = Club(json.load(f))
        df_dist = ex_clb.search(" ".join(player))
        if df_dist.shape[0] > 0:
            match = Player(df_dist.loc[0], "", "", "", "", "", "", pd_row_or_dict=True)
            with open('data_sg/xis/{}.json'.format(str(ctx.author.id)), 'r', encoding='utf-8') as f:
                xi_obj = XI(source=json.load(f))

            empty_ind = ""
            exists = False
            for i in reversed(range(1,12)):
                temp = xi_obj.xi[str(i)]["plr"]
                if temp != "":
                    temp_plr = Player(xi_obj.xi[str(i)]["plr"], "", "", "", "", "", "", pd_row_or_dict=True)
                    if temp_plr.unique_id() == match.unique_id():
                        exists = True
                        break
                if xi_obj.xi[str(i)]["plr"] == "":
                    empty_ind = str(i)

            if empty_ind == "":
                await ctx.send("XI is full.")
            elif exists:
                await ctx.send("Player is already in your XI.")
            else:
                xi_obj.xi[empty_ind]["plr"] = match.to_dict()

                with open('data_sg/xis/{}.json'.format(str(ctx.author.id)), 'w', encoding='utf-8') as f:
                    json.dump(xi_obj.to_dict(), f, ensure_ascii=False, indent=4)
                await ctx.send("{} was added to your XI.".format(match.name))
        else:
            await ctx.send("No match for {}".format(player))

    except Exception as e:
        print(e)
        print(traceback.format_exc())
        await ctx.send("<@{}> Your club does not exist! Type '$sg_claim' to get a player.".format(ctx.author.id))

@bot.command(hidden=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def sg_del(ctx, *player: str):
    try:
        with open('data_sg/clubs/{}.json'.format(str(ctx.author.id)), 'r', encoding='utf-8') as f:
            ex_clb = Club(json.load(f))
        df_dist = ex_clb.search(" ".join(player))
        if df_dist.shape[0] > 0:
            match = Player(df_dist.loc[0], "", "", "", "", "", "", pd_row_or_dict=True)
            with open('data_sg/xis/{}.json'.format(str(ctx.author.id)), 'r', encoding='utf-8') as f:
                xi_obj = XI(source=json.load(f))

            rpl_ind = ""
            for i in range(1, 12):
                temp = xi_obj.xi[str(i)]["plr"]
                if temp != "":
                    temp_plr = Player(xi_obj.xi[str(i)]["plr"], "", "", "", "", "", "", pd_row_or_dict=True)
                    if temp_plr.unique_id() == match.unique_id():
                        rpl_ind = str(i)
                        break

            if rpl_ind != "":
                xi_obj.xi[rpl_ind]["plr"] = ""
                with open('data_sg/xis/{}.json'.format(str(ctx.author.id)), 'w', encoding='utf-8') as f:
                    json.dump(xi_obj.to_dict(), f, ensure_ascii=False, indent=4)
                await ctx.send("{} was removed from your XI.".format(match.name))
            else:
                await ctx.send("{} is not in your XI.".format(match.name))
        else:
            await ctx.send("No match for {}".format(player))

    except Exception as e:
        print(e)
        print(traceback.format_exc())
        await ctx.send("<@{}> Your club does not exist! Type '$sg_claim' to get a player.".format(ctx.author.id))

@bot.command(hidden=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def sg_xi(ctx):
    with open('data_sg/xis/{}.json'.format(str(ctx.author.id)), 'r', encoding='utf-8') as f:
        xi_obj = XI(source=json.load(f))
    await asyncio.wait([ctx.send(file=discord.File(xi_obj.to_img()))])

## error handlers

@sg_claim.error
async def sg_claim_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        msg = 'This command is ratelimited, please try again in {:.2f}s'.format(error.retry_after)
        await ctx.send(msg)
    else:
        raise error

@sg_club.error

async def sg_club_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        msg = "Please specify which page of your club you want. '$sg_club 1' gets the 1st page."
        await ctx.send(msg)
    else:
        raise error

'''
@bot.event
async def on_message(message):
    if message.clean_content.lower().strip() == "thanks jeff":
        await message.channel.send("You're welcome")
'''
bot.run(token)
