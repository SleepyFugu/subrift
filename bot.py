import discord
import json
import api
import asyncio
import random
import typing
from discord.ext import commands

rift_icon  = 'https://cdn.discordapp.com/avatars/699752709028446259/df9496def162ef55bcaa9a2005c75ab2.png?size=256'
songs      = asyncio.Queue()
playNext   = asyncio.Event()
printQueue = []
loglevels  = ["INFO ", "WARN ", "ERROR"]

#Classes
class Player():
    def __init__(self, ctx, vc, song):
        self.ctx = ctx
        self.vc = vc
        self.song = song

    #Start Song
    async def start(self):
        ctx = self.ctx
        vc = self.vc
        song = self.song

        #Check if bot was disconnected.
        if not client.voice_clients:
            await logInfo("Bot was disconnected, clearing queue")
            clearQueue(printQueue)
            client.loop.call_soon_threadsafe(playNext.set)
            return

        embed = discord.Embed(
            title = 'Playing {0} by {1}'.format(song.title, song.artist),
            color = discord.Color.orange(),
            description = '[Download]({0})'.format(api.streamSong(song.id).url)
        )
        embed.set_author(name='SubRift')
        embed.set_footer(text=api.url)
        embed.set_thumbnail(rift_icon)

        #Check cover art
        if song.coverArt != '':
            embed.set_image(url=api.getCoverArt(song.coverArt).url)

        await ctx.send(embed=embed)

        printQueue.pop(0)
        beforeArgs = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        vc.play(discord.FFmpegPCMAudio(
                    source = api.streamSong(song.id).url,
                    before_options = beforeArgs),
                    after = toggleNext
        )

def constrain(val, min, max):
    if val < min:
        return min
    if val > max:
        return max
    return val


def levelToString(level: int):
    return loglevels[constrain(level, 0, len(loglevels)-1)]

async def logInfo(msg):
    print(f"{levelToString(0)} | {msg}")

async def logWarning(msg):
    print(f"{levelToString(1)} | {msg}")

async def logError(msg):
    print(f"{levelToString(2)} | {msg}")

def logFatal(msg):
    print(f"{levelToString(3)} | {msg}")
    exit(1)


async def ignore_self(fn):
    async def wrapped(*args, **kwargs):
        if ctx.author == client.user:
            return
        return fn(*args, **kwargs)
    return wrapped


#Clear Queue
def clearQueue(queue):
    if queue is List:
        queue.clear()
    for _ in range(songs.qsize()):
        songs.get_nowait()
        songs.task_done()


async def require_vc(fn):
    async def wrapped(*args, **kwargs):
        ctx = args[0]

        if ctx is None:
            print("Invalid context, cannot be None")
            return

        if ctx.author.voice is None:
            await ctx.send("You need to join a voice channel first.")
            return

        if not client.voice_clients:
            await (ctx.author.voice.channel).connect()

        return fn(*args, **kwargs)
    return wrapped


async def require_queue(fn):
    async def wrapped(*args, **kwargs):
        ctx = args[0]

        if ctx is None:
            print("Invalid context, cannot be None")
            return

        #Check Queue is not empty
        if len(printQueue) == 0:
            await ctx.send("Queue is empty")
            return

        return fn(*args, **kwargs)
    return wrapped


async def audioPlayer():
    while True:
        #Clear flag and get from queue
        playNext.clear()
        player = await songs.get()
        await player.start()
        await playNext.wait()


#Retrieve data from json file
with open("subrift.json", "r") as read_file:
    data = json.load(read_file)

client = commands.Bot(command_prefix=data["PREFIX"] or 's!')

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")


@client.command()
@ignore_self(fn)
async def ping(ctx):
    """Test bot with a ping
    """
    if ctx.author == client.user:
        return
    await ctx.channel.send('Pong~!')


@client.command()
@commands.is_owner()
async def quit(ctx):
    """Logout of Discord, and exit the bot process
    """
    await ctx.send("This is so sad...")
    await ctx.bot.logout()
    exit(0)


#Toggles next song
def toggleNext(self):
    client.loop.call_soon_threadsafe(playNext.set)


#Next Song
@client.command()
@require_vc(fn)
@require_queue(fn)
@ignore_self(fn)
async def skip():
    vc = client.voice_clients[0]
    if vc.is_playing():
        vc.stop()


#Play Song Discord Command
@client.command()
@require_vc(fn)
@ignore_self(fn)
async def play(ctx, *, query):
    vc = client.voice_clients[0]
    song = api.getSong(query)

    if song is None:
        await ctx.send("Cannot locate song")
        return

    printQueue.append(song)
    await ctx.send('Added to Queue')
    await playSong(ctx, vc, song)

#Play Song
async def playSong(ctx, vc, song):
    if song is None:
        return

    player = Player(ctx, vc, song)
    await songs.put(player)

@client.command()
@require_vc(fn)
@ignore_self(fn)
async def playalbum(ctx, option: typing.Optional[int] = None, *, query):
    """
    """
    vc = client.voice_clients[0]

    album = api.getAlbumData(api.getAlbum(query).id)

    if album is None:
        await ctx.send('Album Not Found. Enter Exact Name')
        return

    if vc.is_playing() == True:
        vc.stop()

    clearQueue(printQueue)

    #Shuffle if -s Given
    if option == 1:
        random.shuffle(album)

    await playSong(ctx, vc, album.pop(0))

    for entry in album:
        printQueue.append(entry)
        await playSong(ctx, vc, entry)



#Stop Song
@client.command()
@require_vc(fn)
@ignore_self(fn)
async def stop(ctx):
    """Stop the currently playing song and clear the queue
    """
    vc = client.voice_clients[0]
    if vc.is_playing() == True:
        vc.stop()
        clearQueue(printQueue)
        await vc.disconnect()
    else:
        await ctx.channel.send('Nothing is playing')


#Pause Song
@client.command()
@require_queue(fn)
@require_vc(fn)
@ignore_self(fn)
async def pause(ctx):
    """Pause the currently playing song
    """
    vc = client.voice_clients[0]
    if vc.is_playing() == True:
        vc.pause()
    else:
        await ctx.channel.send('Nothing is playing')

@client.command()
@require_queue(fn)
@require_vc(fn)
@ignore_self(fn)
async def resume(ctx):
    """Resumes a paused song
    """
    vc = client.voice_clients[0]
    if vc.is_playing() == False:
        vc.resume()
    else:
        await ctx.channel.send('Song is already playing')


@client.command()
@ignore_self(fn)
async def search(ctx, *, query):
    """Search for a particular string on the Subsonic server
    """
    if ctx.author == client.user:
        return

    songInfoList = api.getSearchResults(query)

    #Embed Message
    embed = discord.Embed(
        title = 'Search Results',
        color = discord.Color.orange()
    )
    embed.set_footer(text=api.url)
    embed.set_author(name='SubRift')
    embed.set_thumbnail(rift_icon)

    #Add Field for every song
    for song in songInfoList:
        embed.add_field(
            name=str(song.id),
            value=f"{song.title} - {song.artist}",
            inline=False
        )

    await ctx.send(embed=embed)


#Check Queue
# Note: Based heavily on:
#  https://stackoverflow.com/questions/55075157/discord-rich-embed-buttons
@client.command()
async def queue(ctx):
    """List the current queue
    """
    pages = []
    total = 0

    #Embed Message
    def new_embed():
        e = discord.Embed(
            color     = discord.Color.orange(),
            footer    = api.url,
            author    = '<@SleepyAli#3611>'
            thumbnail = rift_icon
        )
        pages.append(e)
        total = total + 1
        return e

    embed = new_embed()

    #Add Field for every song
    count = 0
    for song in printQueue:
        count = count + 1
        embed.add_field(
            name   = count,
            value  = f"{song.title} - {song.artist}",
            inline = False
        )

        # Split into new embed every 100 entries
        if count-1 >= 100 / total and not count >= len(printQueue):
            embed = new_embed()

    #If theres only one page, just send it and return
    if total == 1:
        pages[0].set_title("Queue")
        return await ctx.send(embed=pages[0])

    for i in range(total):
        pages[i].set_title(f"Queue ({i + 1} of {total})")

    first_react = '⏮'
    prev_react = '◀'
    next_react = '▶'
    last_react = '⏭'

    message = await ctx.send(embed=embed)
    await message.add_reaction(first_react)
    await message.add_reaction(prev_react)
    await message.add_reaction(next_react)
    await message.add_reaction(last_react)

    def check(reaction, user):
        return user == ctx.author

    at_page = 0
    timeout = float(30)
    reaction = None

    while True:
        if str(reaction) == first_react:
            at_page = 0
            await message.edit(embed = pages[at_page])
        elif str(reaction) == prev_react:
            at_page = constrain(at_page - 1, 0, total - 1)
            await message.edit(embed = pages[at_page])
        elif str(reaction) == next_react:
            at_page = constrain(at_page + 1, 0, total - 1)
            await message.edit(embed = pages[at_page])
        elif str(reaction) == last_react:
            at_page = constrain(total, 0, total - 1)
            await message.edit(embed = pages[at_page])

        try:
            reaction, user = await client.wait_for('reaction_add',
                timeout = timeout,
                check   = check,
            )
            await message.remove_reaction(reaction, user)
        except:
            break

    await message.clear_reactions()


@client.command()
@require_vc(fn)
@ignore_self(fn)
async def playlist(ctx, option: typing.Optional[int] = None, *, query):
    """Query for a given playlist, and play it (resets the queue)
    """
    playlist = api.getPlaylist(query)
    if playlist is None:
        await ctx.send('Failed to locate playlist, please enter the exact name')
        return

    vc = client.voice_clients[0]
    if vc.is_playing() == True:
        vc.stop()

    clearQueue(printQueue)

    #Shuffle if -s Given
    # TODO: This doesn't seem to be working, will need to look into why
    if option == 1:
        random.shuffle(playlist)

    await playSong(playlist.pop(0))

    for entry in playlist:
        await playSong(ctx, vc, entry)
        printQueue.append(entry)


@client.command()
@require_vc(fn)
@require_queue(fn)
@ignore_self(fn)
async def shuffle(ctx):
    """Shuffles the currently active song queue"""
    clearQueue()
    random.shuffle(printQueue)
    for entry in printQueue:
        await playSong(ctx, vc, entry)


####################
## Command Errors ##
####################
@play.error
async def play_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Try `play [song-title]`')


if __name__ == '__main__':
    TOKEN = data["DISCORDTOKEN"]
    client.loop.create_task(audioPlayer())
    client.run(TOKEN)