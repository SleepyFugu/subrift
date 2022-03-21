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
    def __init__(self, id='', title='', artist='', album='', coverArt='', path='', element=None):
        if not isinstance(element, ET.Element):
            self.id = id
            self.path = path
            self.title = title
            self.artist = artist
            self.album = album
            self.coverArt = coverArt
            return

        if element.tag != f"{{{ns['sub']}}}music":
            raise TypeError

        for a in ['id', 'title', 'artist', 'album', 'coverArt', 'path']:
            try:
                _ = element.attrib[a]
            except KeyError:
                element.attrib[a] = ''

        self.id = element.attrib['id']
        self.path = element.attrib['path']
        self.title = element.attrib['title']
        self.artist = element.attrib['artist']
        self.album = element.attrib['album']
        self.coverArt = element.attrib['coverArt']


class albumInfo:
    def __init__(self, id='', title='', artist='', coverArt='', element=''):
        if not isinstance(element, ET.Element):
            self.id = id
            self.title = title
            self.artist = artist
            self.coverArt = coverArt
            return

        if element.tag != f"{{{ns['sub']}}}album":
            log.error(f"Got bad tag: {element.tag}")
            raise TypeError

        for a in ['id', 'name', 'artist', 'coverArt']:
            try:
                _ = element.attrib[a]
            except KeyError:
                element.attrib[a] = ''

        self.id = element.attrib['id']
        self.title = element.attrib['name']
        self.artist = element.attrib['artist']
        self.coverArt = element.attrib['coverArt']


class artistInfo:
    def __init__(self, id, name):
        self.id = id
        self.name = name

class playlistInfo:
    def __init__(self, id, title, count, owner, comment):
        self.id = id
        self.title = title
        self.count = count
        self.owner = owner
        self.comment = comment

class searchResults:
    def __init__(self, results:ET.Element, form:int=3):
        if form != 1:
            searchForm = f"searchResult{form}"
        else:
            searchForm = "searchResult"


        self.songs = []
        self.albums = []
        self.artists = []

        if isinstance(results, ET.Element):
            for result in results.findall(f"sub:{searchForm}", namespaces=ns):
                for song in result.findall('sub:song', namespaces=ns):
                    self.songs.append(songInfo(element=song))

                for album in result.findall('sub:album', namespaces=ns):
                    self.albums.append(albumInfo(element=album))

                for artist in result.findall('sub:artist', namespaces=ns):
                    self.artists.append(artistInfo(
                        id = artist.attrib['id'],
                        name = artist.attrib['name'],
                    ))

        self.song_count = len(self.songs)
        self.album_count = len(self.albums)
        self.artist_count = len(self.artists)


def makeXMLRequest(endpoint:str, params=None) -> ET.Element:
    """Perform an http request against an XML endpoint, and return it's root element

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


def search2(query, params:dict={}) -> searchResults:
    """Run a subsonic search2 query

    Returns
    -------
    Element: Query returns
    """
    params["query"] = query
    return searchResults(form=2, results=makeXMLRequest('/rest/search2', params))


def search3(query, params:dict={}) -> searchResults:
    """Run a subsonic search3 query

    Returns
    -------
    Element: Query returns
    """
    params["query"] = query
    return searchResults(form=3, results=makeXMLRequest('/rest/search3', params))

#(binary) Returns request containing song data
def streamSong(id):
    return makeRawRequest("/rest/stream", stream=True, params={
        "id": id
    })

#(binary) Searches song given query and returns the song data
def getSongFromName(query) -> songInfo:
    songs = searchSong(query, count=1)
    if len(songs) < 1:
        return None
    return songs[0]


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

    return songInfo(element=song)


def getAlbum(id) -> list:
    """Return song data for an album

    Returns
    -------
    list[songInfo]: Full list of songs that are in the found album
    """
    element = makeXMLRequest("/rest/getAlbum", {
        "id": id,
    })

    if element is None:
        return None

    #Put All Songs in List
    songInfoList = []
    for album in element.findall("sub:album", namespaces=ns):
        for entry in album.findall("sub:song", namespaces=ns):
            songInfoList.append(songInfo(element=entry))

    return songInfoList


def getPlaylist(id:str) -> list:
    """Return song data for a playlist

    Returns
    -------
    list[songInfo]: Full list of songs that are in the found album
    """
    element = makeXMLRequest('/rest/getPlaylist', {
        "id": id
    })

    if element is None:
        return []

    #Put All Songs in List
    songInfoList = []
    for playlist in element.findall("sub:playlist", namespaces=ns):
        for entry in playlist.findall("sub:entry", namespaces=ns):
            songInfoList.append(songInfo(element=entry))

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


#(binary) Returns request containing raw song data
def getCoverArt(id):
    """Performs a raw request for a cover image using an ID
    """
    return makeRawRequest('/rest/getCoverArt', {"id":id})


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


def searchSong(query, offset:int=0, count:int=20) -> list:
    """Perform a search3 with albums and artists suppressed, and return the songs found

    Supports passing an offset for paging
    """
    return search3(query, {
        "songCount": count,
        "albumCount": 0,
        "artistCount": 0,
        "songOffset": str(offset),
    }).songs


def searchAlbum(query, offset:int=0, count:int=20) -> list:
    """Perform a search3 with songs and artists suppressed, and return the albums found

    Supports passing an offset for paging
    """
    return search3(query, {
        "songCount": 0,
        "albumCount": count,
        "artistCount": 0,
        "albumOffset": str(offset),
    }).albums


def searchArtist(query, offset:int=0, count:int=20) -> list:
    """Perform a search3 with songs and albums suppressed, and return the artists found

    Supports passing an offset for paging
    """
    return search3(query, {
        "songCount": 0,
        "albumCount": 0,
        "artistCount": count,
        "artistOffset": str(offset),
    }).artists
