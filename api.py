import log
import json
import requests
import uuid
import asyncio
import xml.etree.ElementTree as ET
import distutils

from authentication import generateHash, generateSalt

#Retrieve data from json file
with open("subrift.json", "r") as read_file:
    data = json.load(read_file)

username = data["USER"]["USERNAME"]
password = data["USER"]["SUBSONICPASSWORD"]
url = data["URL"]

#Generate Salt, Client, & Hash
salt = generateSalt()
token = generateHash(password, salt)
client = 'Subrift'

#XML Namespaces
ns = {'sub' : 'http://subsonic.org/restapi'}

#Classes
class songInfo:
    def __init__(self, id, title, artist, album, coverArt):
        self.id = id
        self.title = title
        self.artist = artist
        self.album = album
        self.coverArt = coverArt

class albumInfo:
    def __init__(self, id, title, artist, coverArt):
        self.id = id
        self.title = title
        self.artist = artist
        self.coverArt = coverArt

class playlistInfo:
    def __init__(self, id, title, count, owner, comment):
        self.id = id
        self.title = title
        self.count = count
        self.owner = owner
        self.comment = comment


def makeXMLRequest(endpoint:str, params=None) -> ET.Element:
    """"Perform an http request against an XML endpoint, and return it's root element

    If the endpoint reports a failure, but still returns valid XML, the error is logged
    and None is returned

    Returns
    -------
    ET.Element: XML root element on successful request
    None: None is returned upon failure
    """
    endpoint = endpoint.lstrip("/")
    log.debug(f"Requesting {url}/{endpoint} w/ params={params} ...")

    req_params = {
        "u" : username,
        "t" : token,
        "s" : salt,
        "v" : '1.16.0',
        "c" : client
    }

    if isinstance(params, dict):
        for k, v in params.items():
            req_params[k] = v

    r = requests.get(
        url = f"{url}/{endpoint}",
        params = req_params,
    )

    element = ET.fromstring(r.text)
    if not r.ok :
        log.warning(f"Got {r.status_code}, an invalid response: {r.reason}")
        return None

    if not element.attrib['status'] == "ok":
        err = element.find('sub:error', namespaces=ns)
        log.warning(f"XML request failed with code {err.attrib['code']}: {err.attrib['message']}")
        return None

    return element


def makeRawRequest(endpoint:str, params=None, stream=False) -> requests.Response:
    """Make an http request to the Subsonic server and return the raw response object

    If a non-2XX code is received from the server, None is return and the error is logged

    Returns
    -------
    requests.Response: The http response object
    """
    endpoint = endpoint.lstrip("/")
    log.debug(f"Requesting {url}/{endpoint} w/ params={params} ...")

    req_params = {
        "u" : username,
        "t" : token,
        "s" : salt,
        "v" : '1.16.0',
        "c" : client
    }

    if isinstance(params, dict):
        for k, v in params.items():
            req_params[k] = v

    r = requests.get(
        url = f"{url}/{endpoint}",
        params = req_params,
        stream = stream
    )

    if not r.ok:
        log.error(f"Received {r.status_code} from {url}/{endpoint}: {r.reason}")
        return None

    return r


def pingServer():
    """Return the current online status of the Subsonic server

    Returns
    -------
    bool: Online status
    """
    if makeXMLRequest('/rest/ping') is not None:
        return True
    return False


def getLicense() -> bool:
    """Return the current state of the Subsonic license

    Returns
    -------
    bool: License status
    """
    root = makeXMLRequest('/rest/getLicense')
    return distutils.util.strtobool(root[0].attrib['valid'])


#(xml) Returns xml object containing indexes
def getIndexes():
    return makeXMLRequest('/rest/getIndexes')


#(xml) Returns xml object containing music folders
# TODO: Create a musicfolders class and refactor this function
def getMusicFolders() -> ET.Element:
    """
    """
    return makeXMLRequest('/rest/getMusic/Folders')


def getMusicDirectory(id):
    """Returns xml object containing music directory when given id
    """
    return makeXMLRequest('/rest/getMusicDirectory', {"id": id})


def search2(query) -> ET.Element:
    """Run a subsonic search2 query

    Returns
    -------
    Element: Query returns
    """
    return makeXMLRequest('/rest/search2', {
        "query": query
    })

def search3(query) -> ET.Element:
    """Run a subsonic search3 query

    Returns
    -------
    Element: Query returns
    """
    return makeXMLRequest('/rest/search3', {
        "query": query
    })

#(binary) Returns request containing song data
def streamSong(id):
    return makeRawRequest("/rest/stream", stream=True, params={
        "id": id
    })

#(binary) Searches song given query and returns the song data
def getSongFromName(query):
    #Query song & save xml response into root
    root = search3(query)

    #Create songInfo object that will hold song information
    song = None

    #Grab first song
    for result in root.findall("sub:searchResult3", namespaces=ns):
        #Get FIRST song result
        for song in result.findall("sub:song", namespaces=ns):
            #Check for empty attributes
            song_id = ''
            title = ''
            artist = ''
            album = ''
            coverArt = ''
            if 'id' in song.attrib:
                song_id = song.attrib["id"]
            if 'title' in song.attrib:
                title = song.attrib["title"]
            if 'artist' in song.attrib:
                artist = song.attrib["artist"]
            if 'album' in song.attrib:
                album = song.attrib["album"]
            if 'coverArt' in song.attrib:
                coverArt = song.attrib["coverArt"]

            #Create object & break
            song = songInfo(song_id, title, artist, album, coverArt)
            break

    return song


def getSong(id:str) -> songInfo:
    """Return a songInfo given an ID
    """
    element = makeXMLRequest('/rest/getSong', {
        "id": id
    })

    if element is None:
        return None

    song = element.find('sub:song', namespaces=ns)

    if song is None:
        return None

    return songInfo(
        id = song.attrib['id'],
        title = song.attrib['title'],
        album = song.attrib['album'],
        artist = song.attrib['artist'],
        coverArt = song.attrib['coverArt']
    )


def getAlbum(id) -> list:
    """Return song data for an album

    Returns
    -------
    list[songInfo]: Full list of songs that are in the found album
    """
    root = makeXMLRequest("/rest/searchAlbum", {
        "id": id
    })

    #Put All Songs in List
    songInfoList = []
    for album in root.findall("sub:album", namespaces=ns):
        for entry in album.findall("sub:song", namespaces=ns):
            #Check for empty attributes
            song_id = ''
            title = ''
            artist = ''
            album = ''
            coverArt = ''
            if 'id' in entry.attrib:
                song_id = entry.attrib["id"]
            else:
                continue
            if 'title' in entry.attrib:
                title = entry.attrib["title"]
            if 'artist' in entry.attrib:
                artist = entry.attrib["artist"]
            if 'album' in entry.attrib:
                album = entry.attrib["album"]
            if 'coverArt' in entry.attrib:
                coverArt = entry.attrib["coverArt"]

            #Create Object and Append
            songInfoList.append(songInfo(song_id, title, artist, album, coverArt))

    return songInfoList


def getPlaylist(id:str) -> list:
    """Return song data for a playlist

    Returns
    -------
    list[songInfo]: Full list of songs that are in the found album
    """
    root = makeXMLRequest('/rest/getPlaylist', {
        "id": id
    })

    if root is None:
        return []

    #Put All Songs in List
    songInfoList = []
    for playlist in root.findall("sub:playlist", namespaces=ns):
        for entry in playlist.findall("sub:entry", namespaces=ns):
            #Check for empty attributes
            song_id = ''
            title = ''
            artist = ''
            album = ''
            coverArt = ''
            if 'id' in entry.attrib:
                song_id = entry.attrib["id"]
            else:
                continue
            if 'title' in entry.attrib:
                title = entry.attrib["title"]
            if 'artist' in entry.attrib:
                artist = entry.attrib["artist"]
            if 'album' in entry.attrib:
                album = entry.attrib["album"]
            if 'coverArt' in entry.attrib:
                coverArt = entry.attrib["coverArt"]

            #Create Object and Append
            songInfoList.append(songInfo(song_id, title, artist, album, coverArt))
            log.debug(f"Added {title} to response")

    return songInfoList


def getPlaylists() -> list:
    """Get all of the playlists the api has access to

    Returns
    -------
    list[playlistInfo]: Playlists
    """
    root = makeXMLRequest('/rest/getPlaylists')
    playlists = []
    for playlistList in root.findall("sub:playlists", namespaces=ns):
        for playlist in playlistList.findall("sub:playlist", namespaces=ns):
            pl = playlistInfo(
                id    = playlist.attrib['id'],
                title = playlist.attrib['name'],
                count = playlist.attrib['songCount'],
                owner = playlist.attrib['owner'],
                comment = None
            )

            try:
                if not playlist.attrib['comment'] == "No comment":
                    if not playlist.attrib['comment'].strip() == "":
                        pl.comment = playlist.attrib['comment']
            except Exception as e:
                pass
            finally:
                playlists.append(pl)

    return playlists


#(songInfo) Returns an array of songInfo objects that contain song info
def searchSong(query):
    #Query song and save xml response into root
    root = search3(query)

    #Take all results from list as songInfo objects
    songInfoList = []
    for result in root.findall("sub:searchResult3", namespaces=ns):
        for song in result.findall("sub:song", namespaces=ns):
            #Check for empty attributes
            song_id = ''
            title = ''
            artist = ''
            album = ''
            coverArt = ''
            if 'id' in song.attrib:
                song_id = song.attrib["id"]
            else:
                continue
            if 'title' in song.attrib:
                title = song.attrib["title"]
            if 'artist' in song.attrib:
                artist = song.attrib["artist"]
            if 'album' in song.attrib:
                album = song.attrib["album"]
            if 'coverArt' in song.attrib:
                coverArt = song.attrib["coverArt"]

            #Create Object and Append
            songInfoList.append(songInfo(song_id, title, artist, album, coverArt))

    return songInfoList


#(playlistInfo) Returns list of playlist
def searchPlaylist(query) -> list:
    """Get a single playlist

    Returns
    -------
    list[songInfo]: Song data for playlist
    """
    root = makeXMLRequest('/rest/getPlaylists')
    for playlistList in root.findall("sub:playlists", namespaces=ns):
        for playlist in playlistList.findall("sub:playlist", namespaces=ns):
            if(playlist.attrib["name"] == query):
                log.debug(f"Found {query}")
                return getPlaylist(playlist.attrib['id'])

    return None


#(binary) Searches album given query and returns the album
def searchAlbum(query):
    #Query album & save xml response into root
    root = search3(query)

    #Create albumInfo object that will hold song information
    album = None

    #Grab first song
    for result in root.findall("sub:searchResult3", namespaces=ns):
        #Get FIRST song result
        for album in result.findall("sub:album", namespaces=ns):
            #Check for empty attributes
            album_id = ''
            title = ''
            artist = ''
            coverArt = ''
            if 'id' in album.attrib:
                album_id = album.attrib["id"]
            if 'name' in album.attrib:
                title = album.attrib["name"]
            if 'artist' in album.attrib:
                artist = album.attrib["artist"]
            if 'coverArt' in album.attrib:
                coverArt = album.attrib["coverArt"]

            #Create object & break
            album = albumInfo(album_id, title, artist, coverArt)
            break

    return album

#(binary) Returns request containing raw song data
def getCoverArt(id):
    return makeRawRequest('/rest/getCoverArt', {"id":id})
