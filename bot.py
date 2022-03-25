from asyncio import tasks
import re
import discord
import json
import api
import log
import sys
import util
import asyncio
import random
import typing
import traceback
from discord.ext import commands

rift_icon  = 'https://cdn.discordapp.com/avatars/699752709028446259/df9496def162ef55bcaa9a2005c75ab2.png?size=256'
songs      = asyncio.Queue()
tasks      = []
playNext   = asyncio.Event()
printQueue = []
currently_playing = None
param_re = re.compile('^(?P<key>[a-zA-Z0-9]+?)=(?P<value>[^=]+?)$')

#Retrieve data from json file
with open("subrift.json", "r") as read_file:
    data = json.load(read_file)

#Classes
class Player():
    def __init__(self, ctx, vc, song):
        self.vc = vc
        self.ctx = ctx
        self.song = song

    #Start Song
    async def start(self):
        ctx = self.ctx
        vc = self.vc
        song = self.song

        #Check if bot was disconnected.
        if not client.voice_clients:
            log.info("Bot was disconnected, clearing queue")
            clearQueue(printQueue)
            client.loop.call_soon_threadsafe(playNext.set)
            return

        try:
            if data["EMBED_ON_PLAY"]:
                e = PagedEmbed(f"Playing {song.title} by {song.artist}")
                embed = discord.Embed(description=f"[Download]({api.streamSong(song.id).url})")
                if song.coverArt != '':
                    embed.set_image(url=api.getCoverArt(song.coverArt).url)
                e.add_page(embed)
                await e.send(ctx)
        except:
            pass


        printQueue.pop(0)
        global currently_playing
        currently_playing = song
        beforeArgs = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        vc.play(discord.FFmpegPCMAudio(
                    source = api.streamSong(song.id).url,
                    before_options = beforeArgs),
                    after = toggleNext
        )


# Note: Based heavily on:
#  https://stackoverflow.com/questions/55075157/discord-rich-embed-buttons
class PagedEmbed():
    def __init__(self, title:str, pages:list=None, thumbnail:str=rift_icon, author:str="Subrift"):
        self.title = title
        self.page_count = 0
        self.pages = []
        self.thumbnail = thumbnail
        self.author = author
        self.color = discord.Color.dark_orange()
        if isinstance(pages, list):
            self.page_count = len(pages)
            self.pages = pages

    def add_page(self, embed:discord.Embed):
        log.debug(f"Added page to {self.title}")
        self.page_count = self.page_count + 1
        self.pages.append(embed)

    async def send(self, ctx, timeout:int=30):
        for i in range(self.page_count):
            self.pages[i].title = f"{self.title} ({i + 1} of {self.page_count})"
            self.pages[i].color = self.color
            self.pages[i].set_footer(text=api.url)
            self.pages[i].set_author(name=self.author)
            self.pages[i].set_thumbnail(url=self.thumbnail)

        if self.page_count == 1:
            self.pages[0].title = self.title
            return await ctx.send(embed=self.pages[0])

        first_react = '⏮'
        prev_react = '⏪'
        next_react = '⏩'
        last_react = '⏭'

        message = await ctx.send(embed=self.pages[0])
        await message.add_reaction(first_react)
        await message.add_reaction(prev_react)
        await message.add_reaction(next_react)
        await message.add_reaction(last_react)

        def check(_, user):
            nonlocal ctx
            return user == ctx.author

        at_page = 0
        timeout = float(30)
        reaction = None

        while True:
            if str(reaction) == first_react:
                at_page = 0
                await message.edit(embed = self.pages[at_page])
            elif str(reaction) == prev_react:
                at_page = util.constrain(at_page - 1, 0, self.page_count - 1)
                await message.edit(embed = self.pages[at_page])
            elif str(reaction) == next_react:
                at_page = util.constrain(at_page + 1, 0, self.page_count - 1)
                await message.edit(embed = self.pages[at_page])
            elif str(reaction) == last_react:
                at_page = util.constrain(self.page_count, 0, self.page_count - 1)
                await message.edit(embed = self.pages[at_page])

            try:
                reaction, user = await client.wait_for('reaction_add',
                    timeout = timeout,
                    check   = check,
                )
                await message.remove_reaction(reaction, user)
            except:
                break

        await message.clear_reactions()

class DynamicPagedEmbed(PagedEmbed):
    def __init__(self, title:str, pages:list=None, thumbnail:str=rift_icon, author:str="Subrift"):
        super().__init__(title, pages, thumbnail, author)
        self.reactions = []
        self.on_page = 0
        async def on_react_fn(self, ctx, message, reaction):
            pass
        self.on_react_fn = on_react_fn

    def on_react(self, fn):
        self.on_react_fn = fn

    def add_react(self, react):
        self.reactions.append(react)

    def update_pages(self):
        for i in range(self.page_count):
            self.pages[i].title = f"{self.title} ({i + 1} of {self.page_count})"
            self.pages[i].color = self.color
            self.pages[i].set_footer(text=api.url)
            self.pages[i].set_author(name=self.author)
            self.pages[i].set_thumbnail(url=self.thumbnail)

    async def send(self, ctx, timeout:int=30):
        self.update_pages()

        message = await ctx.send(embed=self.pages[0])
        for react in self.reactions:
            await message.add_reaction(react)

        def check(_, user):
            nonlocal ctx
            return user == ctx.author

        timeout = float(30)
        reaction = None

        while True:
            await self.on_react_fn(self, ctx, message, reaction)
            try:
                reaction, user =  await client.wait_for('reaction_add',
                    timeout = timeout,
                    check = check
                )
                await message.remove_reaction(reaction, user)
            except:
                break

        await message.clear_reactions()


#Clear Queue
def clearQueue(queue=None):
    if isinstance(queue, list):
        queue.clear()
    for _ in range(songs.qsize()):
        songs.get_nowait()
        songs.task_done()
    tasks.clear()


def removeFromQueue(position:int):
    for i in range(len(tasks())):
        if i ==  position + 1:
            task = tasks.pop(i)


def plural(n:int) -> str:
    if n != 1:
        return 's'
    return ''


async def require_playing(ctx: discord.ext.commands.Context):
    if not client.voice_clients:
        await ctx.send("There is nothing playing")
        return False
    return True


async def require_vc(ctx: discord.ext.commands.Context):
    if ctx is None:
        log.error("invalid context received")
        return False

    if ctx.author.voice is None:
        await ctx.send("You need to join a voice channel first.")
        return False

    return True


async def require_queue(ctx: discord.ext.commands.Context):
    if ctx is None:
        await log.error("invalid context received")
        return False

    #Check Queue is not empty
    if len(printQueue) == 0:
        await ctx.send("Queue is empty")
        return False

    return True


async def log_command(ctx: discord.ext.commands.Context):
    log.info(f"{ctx.author.name} ran {ctx.command.name}")
    return True


async def ignore_self(ctx: discord.ext.commands.Context):
    if ctx.author == client.user:
        return False
    return True


async def audioPlayer():
    while True:
        #Clear flag and get from queue
        playNext.clear()
        player = await songs.get()
        await player.start()
        await playNext.wait()


#Play Song
async def playSong(ctx, vc, song):
    if song is None:
        return

    player = Player(ctx, vc, song)
    await songs.put(player)


#Toggles next song
def toggleNext(self):
    client.loop.call_soon_threadsafe(playNext.set)

client = commands.Bot(command_prefix=data["PREFIX"] or 's!')

@client.event
async def on_ready():
    log.info(f"Logged in as {client.user}")


#########################
## Command Definitions ##
#########################


@client.command()
@commands.is_owner()
async def toggleDebug(ctx):
    if log.debugEnabled():
        log.disableDebug()
        await ctx.send("Disabled debug logging")
        return
    log.enableDebug()
    await ctx.send("Enabled debug logging")


@client.command()
@commands.is_owner()
async def requestXML(ctx, endpoint, *, parameters_str=None):
    log.debug(f"Got endpoint: {endpoint}")
    log.debug(f"Got params: {parameters_str}")

    params = {}
    if isinstance(parameters_str, str):
        for p in parameters_str.split(" "):
            log.debug(f"Checking param str: {p}")
            m = param_re.match(p)
            if m is None:
                continue

            params[m.group('key')] = m.group('value')

    r = api.makeRawRequest(endpoint, params=params)
    pager = PagedEmbed("XML Response", thumbnail='')
    embed = discord.Embed()

    if r == None:
        embed.description = "Request failed, 'None' recieved"
        pager.add_page(embed)
        return await pager.send(ctx)

    embed.description = f"```xml\n{r.text}```"
    pager.add_page(embed)
    await pager.send(ctx)


@client.command()
@commands.check(log_command)
@commands.check(ignore_self)
async def ping(ctx):
    """Test bot with a ping
    """
    if api.pingServer():
        await ctx.channel.send("Pong~! Subsonic server is up!")
        return
    await ctx.channel.send("Pong~! Subsonic server is down :(")


@client.command()
@commands.is_owner()
async def quit(ctx):
    """Logout of Discord, and exit the bot process
    """
    await ctx.send("This is so sad...")
    await ctx.bot.logout()
    exit(0)


@client.command()
@commands.check(require_playing)
@commands.check(require_vc)
@commands.check(require_queue)
@commands.check(log_command)
@commands.check(ignore_self)
async def skip(ctx):
    """Skip the currently playing song
    """
    vc = client.voice_clients[0]
    if vc.is_playing():
        vc.stop()


@client.command()
@commands.check(require_vc)
@commands.check(log_command)
@commands.check(ignore_self)
async def play(ctx, *, query):
    """Play a song from the subsonic server
    """
    if not client.voice_clients:
        await (ctx.author.voice.channel).connect()

    vc = client.voice_clients[0]
    song = api.getSong(query)

    if not isinstance(song, api.songInfo):
        log.debug(song)
        song = api.getSongFromName(query)
        if not isinstance(song, api.songInfo):
            await ctx.send("Cannot locate song")
            return

    printQueue.append(song)
    await ctx.send('Added to Queue')
    await playSong(ctx, vc, song)


@client.command()
@commands.check(require_vc)
@commands.check(log_command)
@commands.check(ignore_self)
async def add(ctx, what:str, *, query:str):
    """Add an object to the queue

    Object can be a song, playlist, or album
    """

    if query == "":
        await ctx.send("Please provide a query")
        return

    if what not in ["song", "playlist", "album", "artist"]:
        query = f"{what} {query}"
        what = "song"
        return

    if not client.voice_clients:
        await (ctx.author.voice.channel).connect()
    vc = client.voice_clients[0]

    count = 0

    # Just run the song command
    if what == "song" or what == "":
        return await play(ctx, query=query)

    # Playlist is kept separate as the playlist command clears the queue
    elif what == 'playlist':
        playlist = api.searchPlaylist(query)
        count = len(playlist)

        if playlist is None or count < 1:
            await ctx.send('Failed to locate playlist, please enter the exact name')
            return

        # This looks gross, but accounts for Player() popping the queue stack when it starts
        # since we need to keep that in mind, we check whether or not the queue still has
        # more than one song present after playSong is run, and we add it to the queue if
        # there is
        first = playlist.pop(0)
        printQueue.append(first)
        await playSong(ctx, vc, first)

        for entry in playlist:
            await playSong(ctx, vc, entry)
            printQueue.append(entry)

    # Ditto.
    elif what == 'album':
        albums = api.searchAlbum(query, count=1)

        if len(albums) < 1:
            await ctx.send('Failed to locate album, please enter the exact name')
            return

        album = api.getAlbum(albums[0].id)
        count = len(album)
        first = album.pop(0)

        printQueue.append(first)
        await playSong(ctx, vc, first)

        for entry in album:
            await playSong(ctx, vc, entry)
            printQueue.append(entry)

    elif what == "artist":
        artists = api.searchArtist(query, count=1)

        if len(artists) < 1:
            await ctx.send('Failed to locate artist, please enter the exact name')
            return

        songs = api.getSongsByArtist(artists[0].id)
        count = len(songs)
        first = songs.pop(0)

        printQueue.append(first)
        await playSong(ctx, vc, entry)

        for entry in songs:
            await playSong(ctx, vc, entry)
            printQueue.append(entry)

    return await ctx.send(f"Added {count} song{plural(count)} to the queue")


@client.command()
@commands.check(require_vc)
@commands.check(require_queue)
@commands.check(log_command)
@commands.check(ignore_self)
async def remove(ctx, *, query):
    if isinstance(query, str):
        try:
            query = int(query)
        except ValueError:
            # If we can't int(), then we're attempting to clear based on a string
            pass

    if isinstance(query, int):
        query = util.constrain(query - 1, 1, len(tasks))
        if query > len(tasks):
            ctx.send("Requested position is larger than the queue size")
            return

        song = removeFromQueue(query)
        if song is not None:
            ctx.send(f"Removed {song.name} from the queue")
            return

        ctx.send(f"Could not remove song from queue at position {query}")
        return

    if isinstance(query, str):
        ctx.send("String / Regex based removal is not yet implemented")
        return

    # Undefined. Need to determine what to do with incorrect types. This should only
    # ever be a string.
    ctx.send("Undefined branch reached")
    raise(TypeError)


@client.command()
@commands.check(require_vc)
@commands.check(log_command)
@commands.check(ignore_self)
async def playalbum(ctx, option: typing.Optional[int] = None, *, query):
    """Select an album and replace the queue with its contents
    """
    if not client.voice_clients:
        await (ctx.author.voice.channel).connect()

    vc = client.voice_clients[0]

    album = api.getAlbum(api.searchAlbum(query).id)

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
@commands.check(require_vc)
@commands.check(require_playing)
@commands.check(log_command)
@commands.check(ignore_self)
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
@commands.check(require_queue)
@commands.check(require_playing)
@commands.check(require_vc)
@commands.check(log_command)
@commands.check(ignore_self)
async def pause(ctx):
    """Pause the currently playing song
    """
    vc = client.voice_clients[0]
    if vc.is_playing() == True:
        vc.pause()
    else:
        await ctx.channel.send('Nothing is playing')

@client.command()
@commands.check(require_queue)
@commands.check(require_playing)
@commands.check(require_vc)
@commands.check(log_command)
@commands.check(ignore_self)
async def resume(ctx):
    """Resumes a paused song
    """
    vc = client.voice_clients[0]
    if vc.is_playing() == False:
        vc.resume()
    else:
        await ctx.channel.send('Song is already playing')


@client.command()
@commands.check(log_command)
@commands.check(ignore_self)
async def search(ctx, *, query):
    """Search for a given song
    """
    description = "🔎: _Add more search results_\n✅: _Add all results so far to the queue_"
    songs_found = 0
    all_results = []
    songInfoList = api.searchSong(query, count=10)
    embed = discord.Embed(description = description)

    play_react = '✅'
    first_react = '⏮'
    prev_react = '⏪'
    next_react = '⏩'
    last_react = '⏭'
    search_react = '🔎'

    if len(songInfoList) < 1:
        pages = PagedEmbed("Search Results")
        embed.description = "No results found"
        pages.add_page(embed)
        return await pages.send(ctx)

    for song in songInfoList:
        all_results.append(song)
        songs_found = songs_found + 1
        embed.add_field(
            name=f"{songs_found}: {song.title} by {song.artist}",
            value=f"ID: _{song.id}_\nAlbum: _{song.album}_",
            inline=False
        )

    async def on_react_fn(self, ctx, message, reaction):
        nonlocal description
        nonlocal songs_found

        if reaction is None:
            return

        if str(reaction) == search_react:
            embed = discord.Embed(description = description)
            songInfoList = api.searchSong(query, count=10, offset=songs_found)
            if len(songInfoList) < 1:
                return

            for song in songInfoList:
                all_results.append(song)
                songs_found = songs_found + 1
                embed.add_field(
                    name=f"{songs_found}: {song.title} by {song.artist}",
                    value=f"ID: _{song.id}_\nAlbum: _{song.album}_",
                    inline=False
                )

            self.add_page(embed)
            self.update_pages()
            self.on_page = len(self.pages) - 1

            await message.edit(embed = self.pages[self.on_page])
        elif str(reaction) == play_react:
            if not client.voice_clients:
                try:
                    await (ctx.author.voice.channel).connect()
                except AttributeError:
                    await ctx.send("You need to be in voice to do that")
                    return
            vc = client.voice_clients[0]
            for song in all_results:
                printQueue.append(song)
                await playSong(ctx, vc, song)

        elif str(reaction) == first_react:
            self.on_page= 0
            await message.edit(embed = self.pages[self.on_page])
        elif str(reaction) == prev_react:
            self.on_page = util.constrain(self.on_page - 1, 0, self.page_count - 1)
            await message.edit(embed = self.pages[self.on_page])
        elif str(reaction) == next_react:
            self.on_page = util.constrain(self.on_page + 1, 0, self.page_count - 1)
            await message.edit(embed = self.pages[self.on_page])
        elif str(reaction) == last_react:
            self.on_page = util.constrain(self.page_count, 0, self.page_count - 1)
            await message.edit(embed = self.pages[self.on_page])

    dynamic = DynamicPagedEmbed("Search Results")
    dynamic.on_react(on_react_fn)

    dynamic.add_react(play_react)
    dynamic.add_react(first_react)
    dynamic.add_react(prev_react)
    dynamic.add_react(next_react)
    dynamic.add_react(last_react)
    dynamic.add_react(search_react)

    dynamic.add_page(embed)

    await dynamic.send(ctx, timeout=60)


@client.command()
@commands.check(require_vc)
@commands.check(require_queue)
@commands.check(log_command)
@commands.check(ignore_self)
async def queue(ctx):
    """List the current queue
    """
    pages = []
    vc = client.voice_clients[0]

    #Embed Message
    def new_embed():
        nonlocal pages
        nonlocal vc
        e = discord.Embed(
            color     = discord.Color.orange(),
            footer    = api.url,
            description = 'Nothing Playing'
        )

        if isinstance(currently_playing, api.songInfo):
            paused = ''
            if not vc.is_playing():
                paused = ' (paused)'
            e.description = f"**Currently Playing{paused}: {currently_playing.title}**"
            e.description = f"{e.description}\n_{currently_playing.artist}"
            e.description = f"{e.description} - {currently_playing.album}_"

        pages.append(e)
        return e

    embed = new_embed()

    #Add Field for every song
    count = 0
    embedded = 0
    for song in printQueue:
        count = count + 1
        embedded = embedded + 1

        embed.add_field(
            name   = f"{count}: {song.title}",
            value  = f"{song.artist} - {song.album}",
            inline = False
        )

        # Split into new embed every 21 entries
        if embedded >= 10 and count <= len(printQueue):
            embed = new_embed()
            embedded = 0

    return await PagedEmbed("Queue", pages).send(ctx)



@client.command()
@commands.check(ignore_self)
async def playlists(ctx):
    """Query the list of available playlists
    """
    playlists = api.getPlaylists()

    if len(playlists) < 1:
        await ctx.send("No available playlists")
        return

    pages = PagedEmbed("Playlists Available")
    embed = discord.Embed(color=discord.Color.orange())

    def new_embed():
        nonlocal pages
        nonlocal embed
        pages.add_page(embed)
        embed = discord.Embed(color=discord.Color.orange())
        embed.set_thumbnail(url=rift_icon)

    count = 1
    fields = 1
    for pl in playlists:
        value = f"_Songs: {pl.count}\nOwner: {pl.owner}"
        if not pl.comment is None:
            value = f"{value}\n{pl.comment}"
        value = f"{value}_"

        embed.add_field(
            name = f"{count}: {pl.title}",
            value = value,
            inline = False
        )

        if fields % 20 == 0 and not count >= len(playlists):
            new_embed()

        count = count + 1

    pages.add_page(embed)

    return await pages.send(ctx)


@client.command()
@commands.check(require_vc)
@commands.check(ignore_self)
async def playlist(ctx, option:str, *, query):
    """Provides access to various subcommands related to playlists
    """

    if not isinstance(option, str):
        raise TypeError("playlist must be passed an argument")

    if option == '':
        raise ValueError("playlist must be passed an argument")

    if option == 'play':
        playlist = api.searchPlaylist(query)
        if playlist is None or len(playlist) < 1:
            return await ctx.send('Failed to locate playlist, please enter the exact name')

        if not client.voice_clients:
            await (ctx.author.voice.channel).connect()

        vc = client.voice_clients[0]
        if vc.is_playing() == True:
            vc.stop()

        clearQueue(printQueue)

        #Shuffle if -s Given
        # TODO: This doesn't seem to be working, will need to look into why
        if option == 1:
            random.shuffle(playlist)

        await playSong(ctx, vc, playlist.pop(0))

        for entry in playlist:
            await playSong(ctx, vc, entry)
            printQueue.append(entry)

    if option == 'enqueue':
        playlist = api.searchPlaylist(query)
        count = len(playlist)

        if playlist is None or count < 1:
            await ctx.send('Failed to locate playlist, please enter the exact name')
            return

        # This looks gross, but accounts for Player() popping the queue stack when it starts
        # since we need to keep that in mind, we check whether or not the queue still has
        # more than one song present after playSong is run, and we add it to the queue if
        # there is
        first = playlist.pop(0)
        printQueue.append(first)
        await playSong(ctx, vc, first)

    # TODO: Implement playlist command argument processor
    if option == 'create':
        re.compile("^$")
    if option == 'delete':
    if option == 'addSong':
    if option == 'delSong':


@client.command()
@commands.check(require_vc)
@commands.check(require_queue)
@commands.check(ignore_self)
async def shuffle(ctx):
    """Shuffles the currently active song queue"""
    clearQueue()
    random.shuffle(printQueue)
    vc = client.voice_clients[0]
    for entry in printQueue:
        await playSong(ctx, vc, entry)
    await ctx.send("Shuffled queue!")


####################
## Command Errors ##
####################
@client.event
async def on_command_error(ctx:discord.ext.commands.Context, error):
    if isinstance(error, commands.errors.CheckFailure):
        log.info(f"{ctx.author.name} failed to run {ctx.command.name}")
        pass
    else:
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

@play.error
async def play_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Usage: `play [title | song-id]`')


if __name__ == '__main__':
    TOKEN = data["DISCORDTOKEN"]
    client.loop.create_task(audioPlayer())
    client.run(TOKEN)
