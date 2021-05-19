from discord.ext import commands
import discord
import math
import pandas as pd
from numpy import nan
import datetime as dt
import plotly.graph_objects as go
import tweepy
from wol_bot_static import token, teams, ha, pred_cols, twitter_apikey, twitter_secret_apikey, \
    twitter_access_token, twitter_secret_access_token
import asyncio

# token - Discord bot token
# teams - dictionary for converting team code to full team name
# ha    - dictionary for converting h to home and a to away
# pred_ - columns for prediction data

#functions
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


#refresh scores on startup
refresh_scores()

bot = commands.Bot(command_prefix='$')

@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))

@bot.command()
async def ping(ctx):
    latency = bot.latency
    await ctx.send(latency)

@bot.command()
async def neves(ctx):
    await ctx.send("https://gfycat.com/unkemptsorefeline-wolverhampton-wanderers-fc-official-wolves")

@bot.command()
async def fifilza(ctx):
    await ctx.send("https://giphy.com/gifs/fifa-esports-fifa19-fifaeworldcup-j44l37bp45nYTENNNF")

@bot.command()
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

@bot.command()
async def format(ctx):
    results_format = pd.read_csv('data_wol/results.csv')
    nexts = results_format[results_format['wolves'].isnull()]['game']
    next = nexts[min(nexts.index)]
    message = "Command should be formatted as '$score GAMECODE WOLSCORE-OPPSCORE'. Example, '$score mch 2-1' where 'mch' " \
              "translates to 'Manchester City Home'. Next match is {} {} with a game code of '{}'.".format(teams[next[0:2]], ha[next[2]], next)
    await ctx.message.author.send(message)

@bot.command()
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

@bot.command()
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
        fig.write_image("table{}.png".format(i))
        files.append("table{}.png".format(i))

    await asyncio.wait([ctx.send(file=discord.File(f)) for f in files])

@bot.command()
async def refresh(ctx):
    refresh_scores()
    await ctx.send('Scores have been updated.')

@bot.command()
async def tweet(ctx, *, tweet):
    auth = tweepy.OAuthHandler(twitter_apikey, twitter_secret_apikey)
    auth.set_access_token(twitter_access_token, twitter_secret_access_token)
    api = tweepy.API(auth)
    api.update_status(tweet)
    await ctx.send('You tried to Tweet: {}'.format(tweet))

@bot.command()
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

bot.run(token)
