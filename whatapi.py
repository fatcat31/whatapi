# -*- coding: utf_8 -*-
#################################################################################
#
# Name: whatapi.py
#
# Synopsis: Module to manage what.cd as a web service
#
# Description: (a detailed description for software users.)
#
# Copyright 2010 devilcius
#
#                          The Wide Open License (WOL)
#
# Permission to use, copy, modify, distribute and sell this software and its
# documentation for any purpose is hereby granted without fee, provided that
# the above copyright notice and this license appear in all source copies.
# THIS SOFTWARE IS PROVIDED "AS IS" WITHOUT EXPRESS OR IMPLIED WARRANTY OF
# ANY KIND. See http://www.dspguru.com/wide-open-license for more information.
#
#################################################################################


__author__="devilcius"
__date__ ="$Oct 23, 2010 11:21:12 PM$"

import hashlib
from BeautifulSoup import BeautifulSoup
import httplib
import os
import pickle
import re
import urllib
import shelve
import tempfile
import htmlentitydefs
from htmlentitydefs import name2codepoint as n2cp


"""
A list of the implemented webservices (from what.cd )
=====================================

# User

    * user.getUserId
    * user.getInfo

    * user.getTorrentsSeedingByUserId
    * user.getTorrentsSnatchedByUserId
    * user.getTorrentsUploadedByUserId

    * user.specificUserInfo
        Atributes:
        ######## stats ###########
        -joindate
        -lastseen
        -dataup
        -datadown
        -ratio
        -rratio
        ######## percentile ###########
        -uppercentile
        -downpercentile
        -torrentsuppercentile
        -reqfilledpercentile
        -bountyspentpercentile
        -postsmadepercentile
        -artistsaddedpercentile
        -overallpercentile
        ######## community ###########
        -postsmadecom
        -torrentscommentscom
        -collagesstartedcom
        -collagescontrcon
        -reqfilledcom
        -reqvotedcom
        -uploadedcom
        -uniquecom
        -perfectcom
        -seedingcom
        -leechingcom
        -snatchedcom
        -invitedcom
        -artistsaddedcom


# Artist

    * artist.getArtistReleases
    * artist.getArtistImage
    * artist.getArtistInfo
    * artist.getArtistTags
    * artist.getArtistSimilar
    * artist.getArtistRequests

    + artist.setArtistInfo


# Torrent

    * torrent.getTorrentParentId
    * torrent.getTorrentDownloadURL
    * torrent.getTorrentDetails
    * torrent.getTorrentSize
    * torrent.getTorrentSnatched
    * torrent.getTorrentSeeders
    * torrent.getTorrentLeechers
    * torrent.getTorrentUploadedBy
    * torrent.getTorrentFolderName
    * torrent.getTorrentFileList
    * torrent.getTorrentDescription
    * torrent.isTorrentFreeLeech
    * torrent.isTorrentReported


# Authenticate

    * authenticate.getAuthenticatedUserId
    * authenticate.getAuthenticatedUserAuthCode
    * authenticate.getAuthenticatedUserDownload
    * authenticate.getAuthenticatedUserUpload()
    * authenticate.getAuthenticatedUserRatio
    * authenticate.getAuthenticatedUserRequiredRatio

"""

class ResponseBody:
    """A Response Body Object"""
    pass

class SpecificInformation:
    """A Specific Information Object"""
    pass


class WhatBase(object):
    """An abstract webservices object."""
    whatcd = None

    def __init__(self, whatcd):
        self.whatcd = whatcd
        #if we are not autenticated in what.cd, do it now
        if not self.whatcd.isAuthenticated():
            print "authenticating..."
            self.whatcd.headers = Authenticate(self.whatcd).getAuthenticatedHeader()

    def _request(self,type, path, data, headers):
        return Request(self.whatcd,type,path,data,headers)

    def _parser(self):
        return Parser(self.whatcd)

    def utils(self):
        return Utils()


class Utils():

    def md5(self, text):
        """Returns the md5 hash of a string."""

        h = hashlib.md5()
        h.update(self._string(text))

        return h.hexdigest()

    def _unicode(self, text):
        if type(text) == unicode:
            return text

        if type(text) == int:
            return unicode(text)

        return unicode(text, "utf-8")

    def _string(self, text):
        if type(text) == str:
            return text

        if type(text) == int:
            return str(text)

        return text.encode("utf-8")

    def _number(self,string):
        """
            Extracts an int from a string. Returns a 0 if None or an empty string was passed
        """

        if not string:
            return 0
        elif string == "":
            return 0
        else:
            try:
                return int(string)
            except ValueError:
                return float(string)

    def substituteEntity(self, match):
        ent = match.group(2)
        if match.group(1) == "#":
            return unichr(int(ent))
        else:
            cp = n2cp.get(ent)

            if cp:
                return unichr(cp)
            else:
                return match.group()

    def decodeHTMLEntities(self, string):
        entity_re = re.compile("&(#?)(\d{1,5}|\w{1,8});")
        return entity_re.subn(self.substituteEntity, string)[0]



class WhatCD(object):

	def __init__(self, username, password, site, loginpage, headers):

            #credentials
            self.username = username
            self.password = password
            self.site = site
            self.loginpage = loginpage
            self.headers = headers
            self.authenticateduserinfo = {}

            self.cache_backend = None
            self.proxy_enabled = False
            self.proxy = None

        def isAuthenticated(self):
            """
                Checks if we are authenticated in what.cd
            """
            if "id" in self.authenticateduserinfo:
                return True
            else:
                return False

        def getCredentials(self):
            """
                Returns an authenticated user credentials object
            """
            return Authenticate(self)


        def getUser(self, username):
            """
                Returns an user object
            """
            return User(username, self)

        def getTorrent(self, id):
            """
                Returns a torrent object
            """
            return Torrent(id, self)

        def getArtist(self, name):
            """
                Returns an artist object
            """
            return Artist(name, self)

        def enableProxy(self, host, port):
            """Enable a default web proxy"""
            self.proxy = [host, Utils()._number(port)]
            self.proxy_enabled = True

        def disableProxy(self):
            """Disable using the web proxy"""
            self.proxy_enabled = False

        def isProxyEnabled(self):
            """Returns True if a web proxy is enabled."""
            return self.proxy_enabled

        def getProxy(self):
            """Returns proxy details."""
            return self.proxy

        def enableCaching(self, file_path = None):
            """Enables caching request-wide for all cachable calls.
            * file_path: A file path for the backend storage file. If
            None set, a temp file would probably be created, according the backend.
            """
            if not file_path:
                file_path = tempfile.mktemp(prefix="whatapi_tmp_")

            self.cache_backend = _ShelfCacheBackend(file_path)

        def disableCaching(self):
            """Disables all caching features."""
            self.cache_backend = None

        def isCachingEnabled(self):
            """Returns True if caching is enabled."""

            return not (self.cache_backend == None)

        def getCacheBackend(self):

            return self.cache_backend

def getWhatcdNetwork(username = "", password = ""):
    """
    Returns a preconfigured WhatCD object for what.cd
    # Parameters:
        * username str: a username of a valid what.cd user
        * password str: user's password
    """

    return WhatCD (
                    username = username,
                    password = password,
                    site = "what.cd",
                    loginpage = "/login.php",
                    headers = {
                        "Content-type": "application/x-www-form-urlencoded",
                        'Accept-Charset': 'utf-8',
                        'User-Agent': "whatapi"
                        })



class _ShelfCacheBackend(object):
    """Used as a backend for caching cacheable requests."""
    def __init__(self, file_path = None):
        self.shelf = shelve.open(file_path)

    def getHTML(self, key):
        return self.shelf[key]

    def setHTML(self, key, xml_string):
        self.shelf[key] = xml_string

    def hasKey(self, key):
        return key in self.shelf.keys()


class Request(object):
    """web service operation."""

    def __init__(self, whatcd,type, path, data, headers):

        self.whatcd = whatcd
        self.utils = Utils()
        self.type = type
        self.path = path
        self.data = data
        self.headers = headers
        #enable catching?
        if whatcd.isCachingEnabled():
            self.cache = whatcd.getCacheBackend()

    def getCacheKey(self):
        """The cache key is a md5 hash of request params."""

        key = self.type + self.path + self.data
        return Utils().md5(key)

    def getCachedResponse(self):
        """Returns a file object of the cached response."""

        if not self.isCached():
            response = self.downloadResponse()
            self.cache.setHTML(self.getCacheKey(), response)
        return self.cache.getHTML(self.getCacheKey())

    def isCached(self):
        """Returns True if the request is already in cache."""

        return self.cache.hasKey(self.getCacheKey())

    def downloadResponse(self):
        """Returns a ResponseBody object from the server."""

        print "downloading from %s" % (self.path)
        conn = httplib.HTTPConnection(self.whatcd.site)
        rb = ResponseBody()

        if self.whatcd.isProxyEnabled():
            conn = httplib.HTTPConnection(host = self.whatcd.getProxy()[0], port = self.whatcd.getProxy()[1])
            conn.request(method = self.type, url="http://" + self.whatcd.site + self.path, body = self.data, headers = self.headers)
        else:
            conn.request(self.type, self.path, self.data, self.headers)

        response = conn.getresponse()
        rb.headers = response.getheaders()
        # Rip all inline JavaScript out of the response in case it hasn't been properly escaped
        rb.body = re.sub('<script type="text/javascript">[^<]+</script>', '', response.read())
        conn.close()
        return rb

    def execute(self, cacheable = False):
        """Depending if caching is enabled, returns response from the server or, if available, the cached response"""
        if self.whatcd.isCachingEnabled() and cacheable:
            response = self.getCachedResponse()
        else:
            response = self.downloadResponse()

        return response

class Authenticate(WhatBase):

    def __init__(self, whatcd):
        """Create an authenticated user object.
        # Parameters:
            * whatcd object: WhatCD object.
        """
        self.whatcd = whatcd
        self.parser = Parser(whatcd)
        if not self.whatcd.isAuthenticated():
            self.getAuthenticatedHeader()


    def getAuthenticatedHeader(self):
        """
            Log user in what.cd and returns the authenticated header
        """
        homepage = None
        #NB: cookie to avoid creating a lot of server sessions while testing this module
        #TODO: remove it or set it as an option, and set loginform['keeplogged'] = 0?
        if os.path.exists("cookie"):
            f = open("cookie", "r")
            self.whatcd.headers = pickle.load(f)
        else:
            print "creating cookie"
            f = open('cookie', 'w')
            loginform= {'username': self.whatcd.username, 'password': self.whatcd.password \
                    , 'keeplogged': '1', 'login': 'Login'}
            data = urllib.urlencode(loginform)
            response = self._request("POST", self.whatcd.loginpage, data, self.whatcd.headers).execute(True)
            try:
                cookie=dict(response.headers)['set-cookie']
                session=re.search("session=[^;]+", cookie).group(0)
                self.whatcd.headers = { "Cookie": session }
                homepage = response.body
                pickle.dump(self.whatcd.headers, f)
            except (KeyError, AttributeError):
                # Login failed, most likely bad creds or the site is down, nothing to do
                print "login failed"
                self.whatcd.headers = None
        f.close()

        #set authenticated user info
        if 'id' not in self.whatcd.authenticateduserinfo:
            self.whatcd.authenticateduserinfo = self.getAuthenticatedUserInfo(homepage)

        return self.whatcd.headers

    def getAuthenticatedUserInfo(self, homepage = None):
        """
            Returns authenticated user's info
        """
        if not homepage:
            homepage = BeautifulSoup(self._request("GET", "/index.php", "", self.whatcd.headers).execute(True).body)
        authuserinfo = self._parser().authenticatedUserInfo(homepage.find("div", {"id": "userinfo"}))
        return authuserinfo

    def getAuthenticatedUserId(self):
        """
            Returns authenticated user's id
        """
        return self.whatcd.authenticateduserinfo["id"]

    def getAuthenticatedUserAuthCode(self):
        """
            Returns authenticated user's authcode
        """
        return self.whatcd.authenticateduserinfo["authcode"]


    def getAuthenticatedUserUpload(self):
        """
            Returns authenticated user's total uploaded data
        """
        return self.whatcd.authenticateduserinfo["uploaded"]


    def getAuthenticatedUserDownload(self):
        """
            Returns authenticated user's total downloaded data
        """
        return self.whatcd.authenticateduserinfo["downloaded"]


    def getAuthenticatedUserRatio(self):
        """
            Returns authenticated user's ratio
        """
        return self.whatcd.authenticateduserinfo["ratio"]

    def getAuthenticatedUserRequiredRatio(self):
        """
            Returns authenticated user's required ratio
        """
        return self.whatcd.authenticateduserinfo["required"]


class User(WhatBase):
    """A What.CD user"""

    def __init__(self, username, whatcd):
        """Create an user object.
        # Parameters:
            * username str: The user's name.
            - whatcd object: the what.cd network object
        """
        WhatBase.__init__(self, whatcd)
        self.name = username
        self.whatcd = whatcd
        self.userpage = "/user.php?"
        self.userid = None
        self.userinfo = None

    def getUserName(self):
        """
            Returns user's name
        """
        return self.username

    def getUserId(self):
        """
            Returns user's id, None if user doesn't exists
        """
        if self.userid:
            return self.userid
        else:
            idform = {'action': "search", 'search': self.name}
            data = urllib.urlencode(idform)
            headers = self._request("GET", self.userpage + data, "", self.whatcd.headers).execute(True).headers
            if dict(headers) is None:
                return None
            else:
                self.userid = dict(headers)['location'][12:]
                return self.userid

    def getInfo(self):
        """
            Returns a dictionary of {percentile:{dataup str,
                                                 datadown str,
                                                 overall str,
                                                 postmade str,
                                                 boutyspent str,
                                                 reqfilled str,
                                                 artistsadded str,
                                                 torrentsup str},
                                     stats: {uploaded str,
                                             ratio str,
                                             joined str,
                                             downloaded str,
                                             lastseen str,
                                             rratio str},
                                     community: {uploaded tuple(total str, url str),
                                                 forumposts tuple(total str, url str),
                                                 invited tuple (total,None),
                                                 perfectflacs tuple(total str, url str),
                                                 contributedcollages tuple(total str, url str),
                                                 reqvoted tuple(total str, url str),
                                                 uniquegroups tuple(total str, url str)
                                                 torrentscomments tuple(total str, url str),
                                                 snatched tuple(total str, url str),
                                                 artists str,
                                                 reqfilled tuple(total str, url str),
                                                 startedcollages tuple(total str, url str),
                                                 leeching tuple(total str, url str),
                                                 seeding tuple(total str, url str)}
                                                }
            If paranoia is not Off, it returns None.
        """
        if self.getUserId():
            form = {'id': self.getUserId()}
            data = urllib.urlencode(form)
            userpage = BeautifulSoup(self._request("GET", self.userpage + data, "", self.whatcd.headers).execute(True).body)
            info = self._parser().userInfo(userpage.find("div", {"class": "sidebar"}), self.name)
            self.userinfo = info
            return info
        else:
            print "no user id retrieved"
            return None


    def getTorrentsSeedingByUserId(self,userid,page=1):
        """
            Returns a list with all user's uploaded music torrents
            in form of dictionary {page(tuple with current and total),tag, dlurl, id,
            artist(a tuple with 1 artist name || 2 names in case of two artists || 'Various Artists' if V.A.},
            album and artistid (a tuple with 1 artist id || 2 ids if 2 artists torrent || empty if V.A.}
        """

        url = "/torrents.php?type=seeding&userid=%s&page=%d" % (userid,page)
        torrentspage = BeautifulSoup(self._request("GET", url, "", self.whatcd.headers).execute(True).body)
        return self._parser().torrentsList(torrentspage)

    def getTorrentsSnatchedByUserId(self,userid,page=1):
        """
            Returns a list with all user's uploaded music torrents
            in form of dictionary {page(tuple with current and total),tag, dlurl, id,
            artist(a tuple with 1 artist name || 2 names in case of two artists || 'Various Artists' if V.A.},
            album and artistid (a tuple with 1 artist id || 2 ids if 2 artists torrent || empty if V.A.}
        """
        url = "/torrents.php?type=snatched&userid=%s&page=%d" % (userid,page)
        torrentspage = BeautifulSoup(self._request("GET", url, "", self.whatcd.headers).execute(True).body)
        return self._parser().torrentsList(torrentspage)

    def getTorrentsUploadedByUserId(self,userid,page=1):
        """
            Returns a list with all user's uploaded music torrents
            in form of dictionary {page(tuple with current and total),tag, dlurl, id,
            artist(a tuple with 1 artist name || 2 names in case of two artists || 'Various Artists' if V.A.},
            album and artistid (a tuple with 1 artist id || 2 ids if 2 artists torrent || empty if V.A.}
        """
        url = "/torrents.php?type=uploaded&userid=%s&page=%d" % (userid,page)
        torrentspage = BeautifulSoup(self._request("GET", url, "", self.whatcd.headers).execute(True).body)
        return self._parser().torrentsList(torrentspage)



    ###############################################
    #              specific values                #
    ###############################################


    def specificUserInfo(self):
        """
            Returns specific attributes of user info. None if user's paranoia is on
        """

        info = SpecificInformation()
        # Initialize attributes
        info.joindate, info.lastseen, info.dataup, info.datadown,\
            info.ratio, info.rratio,info.uppercentile,info.downpercentile, \
            info.torrentsuppercentile,info.reqfilledpercentile,info.bountyspentpercentile, \
            info.postsmadepercentile,info.artistsaddedpercentile,info.overallpercentile, \
            info.postsmadecom,info.torrentscommentscom,info.collagesstartedcom,info.collagescontrcon, \
            info.reqfilledcom,info.reqvotedcom,info.uploadedcom,info.uniquecom, info.perfectcom, \
            info.seedingcom, info.leechingcom,info.snatchedcom,info.invitedcom,info.artistsaddedcom \
            = (None,None, None, None,None,None,None,None,None,None,None,None,None, None,\
                None,None,None,None,None,None,None,None,None,None,None,None,None,None)


        if not self.userinfo and self.getInfo() is None:
            pass
        else:
            ######## stats ###########
            info.joindate = self.userinfo['stats']['joined']
            info.lastseen = self.userinfo['stats']['lastseen']
            info.dataup = self.userinfo['stats']['uploaded']
            info.datadown =  self.userinfo['stats']['downloaded']
            info.ratio = self.userinfo['stats']['ratio']
            info.rratio = self.userinfo['stats']['rratio']
            ######## percentile ###########
            info.uppercentile = self.userinfo['percentile']['dataup']
            info.downpercentile = self.userinfo['percentile']['datadown']
            info.torrentsuppercentile = self.userinfo['percentile']['torrentsup']
            info.reqfilledpercentile = self.userinfo['percentile']['reqfilled']
            info.bountyspentpercentile = self.userinfo['percentile']['bountyspent']
            info.postsmadepercentile = self.userinfo['percentile']['postsmade']
            info.artistsaddedpercentile = self.userinfo['percentile']['artistsadded']
            info.overallpercentile = self.userinfo['percentile']['overall']
            ######## community ###########
            info.postsmadecom = self.userinfo['community']['forumposts']
            info.torrentscommentscom = self.userinfo['community']['torrentscomments']
            info.collagesstartedcom = self.userinfo['community']['startedcollages']
            info.collagescontrcon = self.userinfo['community']['contributedcollages']
            info.reqfilledcom = self.userinfo['community']['reqfilled']
            info.reqvotedcom = self.userinfo['community']['reqvoted']
            info.uploadedcom = self.userinfo['community']['uploaded']
            info.uniquecom = self.userinfo['community']['uniquegroups']
            info.perfectcom = self.userinfo['community']['pefectflacs']
            info.seedingcom = self.userinfo['community']['seeding']
            info.leechingcom = self.userinfo['community']['leeching']
            info.snatchedcom = self.userinfo['community']['snatched']
            info.invitedcom = self.userinfo['community']['invited'][0]
            info.artistsaddedcom = self.userinfo['community']['artists']



        return info


class Torrent(WhatBase):
    """A What.CD torrent"""

    def __init__(self, id, whatcd):
        """Create a torrent object.
        # Parameters:
            * id str: The torrent's id.
            * whatcd object: the WhatCD network object
        """
        WhatBase.__init__(self, whatcd)
        self.id = id
        self.whatcd = whatcd
        self.torrentspage = "/torrents.php?"
        self.torrentinfo = self.getInfo()

    def getTorrentUrl(self):
        """
            Returns a dictionnary torrent's real URL
        """
        form = {'torrentid': self.id}
        data = urllib.urlencode(form)
        headers = self._request("GET", self.torrentspage + data, "", self.whatcd.headers).execute(True).headers
        if dict(headers) is None:
            return None
        else:
            return dict(headers)['location']

    def getInfo(self):
        """
            Returns a dictionnary with torrents's info
        """
        if self.getTorrentUrl():
            torrentpage = BeautifulSoup(self._request("GET", "/"+self.getTorrentUrl(), "", self.whatcd.headers).execute(True).body)
            return self._parser().torrentInfo(torrentpage, self.id)
        else:
            return None
            print "no user id retrieved"


    def getTorrentParentId(self):
        """
            Returns torrent's group id
        """
        return self.torrentinfo['torrent']['parentid']

    def getTorrentDownloadURL(self):
        """
            Returns relative url to download the torrent
        """
        return self.torrentinfo['torrent']['downloadurl']

    def getTorrentDetails(self):
        """
            Returns torrent's details (format / bitrate / media)
        """
        return self.torrentinfo['torrent']['details']

    def getTorrentSize(self):
        """
            Returns torrent's size
        """
        return self.torrentinfo['torrent']['size']


    def getTorrentSnatched(self):
        """
            Returns torrent's total snatches
        """
        return self.torrentinfo['torrent']['snatched']


    def getTorrentSeeders(self):
        """
            Returns torrent's current seeders
        """
        return self.torrentinfo['torrent']['seeders']

    def getTorrentLeechers(self):
        """
            Returns torrent's current leechers
        """
        return self.torrentinfo['torrent']['leechers']

    def getTorrentUploadedBy(self):
        """
            Returns torrent's uploader
        """
        return self.torrentinfo['torrent']['uploadedby']

    def getTorrentFolderName(self):
        """
            Returns torrent's folder name
        """
        return self.torrentinfo['torrent']['foldername']

    def getTorrentFileList(self):
        """
            Returns torrent's file list
        """
        return self.torrentinfo['torrent']['filelist']


    def getTorrentDescription(self):
        """
            Returns torrent's description / empty string is there's none
        """
        return self.torrentinfo['torrent']['torrentdescription']

    def isTorrentFreeLeech(self):
        """
            Returns True if torrent is freeleeech, False if not
        """
        return self.torrentinfo['torrent']['isfreeleech']

    def isTorrentReported(self):
        """
            Returns True if torrent is reported, False if not
        """
        return self.torrentinfo['torrent']['isreported']


class Artist(WhatBase):
    """A What.CD artist"""

    def __init__(self, name, whatcd):
        """Create an artist object.
        # Parameters:
            * name str: The artist's name.
            * whatcd object: The WhatCD network object
        """
        WhatBase.__init__(self, whatcd)
        self.name = name
        self.whatcd = whatcd
        self.artistpage = "/artist.php"
        self.utils = Utils()
        self.info = self.getInfo()


    def getArtistName(self):
        """
            Returns artist's name
        """
        return self.name

    def getArtistId(self):
        """
            Returns artist's id, None if artist's not found
        """
        form = {'artistname': self.name}
        data = urllib.urlencode(form)
        headers = self._request("GET", self.artistpage +"?"+ data, "", self.whatcd.headers).execute(True).headers
        if dict(headers)['location'][0:14] != 'artist.php?id=':
            return None
        else:
            return dict(headers)['location'][14:]

    def getInfo(self):
        """
            Returns artist's info, None if there isn't
        """
        if self.getArtistId():
            form = {'id': self.getArtistId()}
            data = urllib.urlencode(form)
            artistpage = BeautifulSoup(self._request("GET", self.artistpage +"?"+ data, "", self.whatcd.headers).execute(True).body)
            return self._parser().artistInfo(artistpage)
        else:
            print "no artist info retrieved"
            return None

    def getArtistReleases(self):
        """
            Returns a list with all artist's releases in form of dictionary {releasetype, year, name, id}
        """
        return self.info['releases']

    def getArtistImage(self):
        """
            Return the artist image URL, None if there's no image
        """
        return self.info['image']

    def getArtistInfo(self):
        """
            Return the artist's info, blank string if none
        """
        return self.info['info']

    def getArtistTags(self):
        """
            Return a list with artist's tags
        """
        return self.info['tags']

    def getArtistSimilar(self):
        """
            Return a list with artist's similar artists
        """
        return self.info['similarartists']

    def getArtistRequests(self):
        """
            Returns a list with all artist's requests in form of dictionary {requestname, id}
        """
        return self.info['requests']

    def setArtistInfo(self, id, info):
        """
            Updates what.cd artist's info and image
            Returns 1 if artist info updated succesfully, 0 if not.
        # Parameters:
            * id str: what.cd artist's id
            * info tuple: (The artist's info -str-, image url -str- (None if there isn't))
        """
        if info[0]:
            params = {'action': 'edit','artistid':id}
            data = urllib.urlencode(params)

            edit_page = BeautifulSoup(self._request("GET", self.artistpage +"?"+ data, "", self.whatcd.headers).execute(True).body)
            what_form = self._parser().whatForm(edit_page,'edit')
            if info[1]:
                image_to_post = info[1]
            else:
                image_to_post = what_form['image']
            data_to_post = {'body': info[0].encode('utf-8'),
                            'summary':'automated artist info insertion',\
                            'image':image_to_post,\
                            'artistid':what_form['artistid'],\
                            'auth':what_form['auth'],\
                            'action':what_form['action']}

            #post artist's info
            self.whatcd.headers['Content-type']="application/x-www-form-urlencoded"
            response = self._request("POST", self.artistpage, urllib.urlencode(data_to_post), self.whatcd.headers).execute(False)
            artist_id_returned = dict(response.headers)['location'][14:]

            if str(artist_id_returned) == str(what_form['artistid']) :
                return 1
            else:
                return 0

        else:
             return 'no artist info provided. Aborting.'
             exit()


class Parser(object):

        def __init__(self,whatcd):
            self.utils = Utils()
            self.whatcd = whatcd

	def authenticatedUserInfo(self, dom):
            """
                Parse the index page and returns a dictionnary with basic authenticated user information
            """
            userInfo = {}
            soup = BeautifulSoup(str(dom))
            for ul in soup.fetch('ul'):
                if ul["id"] == "userinfo_username":
                    #retrieve user logged id
                    hrefid = ul.findAll('li')[0].find("a")["href"]
                    regid = re.compile('[0-9]+')
                    if regid.search(hrefid) is None:
                        self.debugMessage("not found  href to retrieve user id")
                    else:
                        userInfo["id"] = regid.search(hrefid).group(0)

                    #retrieve user logged id
                    hrefauth = ul.findAll('li')[2].find("a")["href"]
                    regauth = re.compile('=[0-9a-fA-F]+')
                    if regid.search(hrefid) is None:
                        self.debugMessage("not found  href to retrieve user id")
                    else:
                        userInfo["authcode"] = regauth.search(hrefauth).group(0)[1:]

                elif ul["id"] == "userinfo_stats":
                    if len(ul.findAll('li')) > 0:
                        userInfo["uploaded"] = ul.findAll('li')[0].find("span").string
                        userInfo["downloaded"] = ul.findAll('li')[1].find("span").string
                        userInfo["ratio"] = ul.findAll('li')[2].findAll("span")[1].string
                        userInfo["required"] = ul.findAll('li')[3].find("span").string
                        userInfo["authenticate"] = True

            return userInfo

	def userInfo(self, dom, user):
            """
                Parse an user's page and returns a dictionnary with its information

            # Parameters:
                * dom str: user page html
                * user str: what.cd username
            """
            userInfo = {'stats':{}, 'percentile':{}, 'community':{}}
            soup = BeautifulSoup(str(dom))

            for div in soup.fetch('div',{'class':'box'}):

                #if paronoia is not set to 'Off', stop collecting data
                if div.findAll('div')[0].string == "Personal":
                    if div.find('ul').findAll('li')[1].contents[1].string.strip() != "Off":
                        return None

            userInfo['stats']['joined'] = soup.findAll('li')[0].find('span')['title']
            userInfo['stats']['lastseen'] = soup.findAll('li')[1].find('span')['title']
            userInfo['stats']['uploaded'] = soup.findAll('li')[2].string[10:]
            userInfo['stats']['downloaded'] = soup.findAll('li')[3].string[12:]
            userInfo['stats']['ratio'] = soup.findAll('li')[4].find('span').string
            userInfo['stats']['rratio'] = soup.findAll('li')[5].string[16:]
            userInfo['percentile']['dataup'] = soup.findAll('li')[6].string[15:]
            userInfo['percentile']['datadown'] = soup.findAll('li')[7].string[17:]
            userInfo['percentile']['torrentsup'] = soup.findAll('li')[8].string[19:]
            userInfo['percentile']['reqfilled'] = soup.findAll('li')[9].string[17:]
            userInfo['percentile']['bountyspent'] = soup.findAll('li')[10].string[14:]
            userInfo['percentile']['postsmade'] = soup.findAll('li')[11].string[12:]
            userInfo['percentile']['artistsadded'] = soup.findAll('li')[12].string[15:]
            userInfo['percentile']['overall'] = soup.findAll('li')[13].find('strong').string[14:]
            '''community section. Returns a tuple (stats,url)
            if user == authenticated user, sum 2 to array position to skip email and passkey <li>s
            shown in personal information'''
            if user == self.whatcd.username:i = 2
            else:i = 0
            userInfo['community']['forumposts'] = (soup.findAll('li')[16+i].contents[0].string[13:len(soup.findAll('li')[16+i].contents[0].string)-2],\
                                                        soup.findAll('li')[16+i].find('a')['href'])
            userInfo['community']['torrentscomments'] = (soup.findAll('li')[17+i].contents[0].string[18:len(soup.findAll('li')[17+i].contents[0].string)-2],\
                                                        soup.findAll('li')[17+i].find('a')['href'])
            userInfo['community']['startedcollages'] = (soup.findAll('li')[18+i].contents[0].string[18:len(soup.findAll('li')[18+i].contents[0].string)-2],\
                                                        soup.findAll('li')[18+i].find('a')['href'])
            userInfo['community']['contributedcollages'] = (soup.findAll('li')[19+i].contents[0].string[25:len(soup.findAll('li')[19+i].contents[0].string)-2],\
                                                        soup.findAll('li')[19+i].find('a')['href'])
            userInfo['community']['reqfilled'] = (soup.findAll('li')[20+i].contents[0].string[17:len(soup.findAll('li')[20+i].contents[0].string)-2],\
                                                        soup.findAll('li')[20+i].find('a')['href'])
            userInfo['community']['reqvoted'] = (soup.findAll('li')[21+i].contents[0].string[16:len(soup.findAll('li')[21+i].contents[0].string)-2],\
                                                        soup.findAll('li')[21+i].find('a')['href'])
            userInfo['community']['uploaded'] = (soup.findAll('li')[22+i].contents[0].string[10:len(soup.findAll('li')[22+i].contents[0].string)-2],\
                                                        soup.findAll('li')[22+i].find('a')['href'])
            userInfo['community']['uniquegroups'] = (soup.findAll('li')[23+i].contents[0].string[15:len(soup.findAll('li')[23+i].contents[0].string)-2],\
                                                        soup.findAll('li')[23+i].find('a')['href'])
            userInfo['community']['pefectflacs'] = (soup.findAll('li')[24+i].contents[0].string[16:len(soup.findAll('li')[24+i].contents[0].string)-2],\
                                                        soup.findAll('li')[24+i].find('a')['href'])
            userInfo['community']['seeding'] = (soup.findAll('li')[25+i].contents[0].string[9:len(soup.findAll('li')[25+i].contents[0].string)-2],\
                                                        soup.findAll('li')[25+i].find('a')['href'])
            userInfo['community']['leeching'] = (soup.findAll('li')[26+i].contents[0].string[10:len(soup.findAll('li')[26+i].contents[0].string)-2],\
                                                        soup.findAll('li')[26+i].find('a')['href'])
            #NB: there's a carriage return and white spaces inside the snatched li tag
            userInfo['community']['snatched'] = (soup.findAll('li')[27+i].contents[0].string[10:len(soup.findAll('li')[27+i].contents[0].string)-7],\
                                                        soup.findAll('li')[27+i].find('a')['href'])
            userInfo['community']['invited'] = (soup.findAll('li')[28+i].contents[0].string[9:],\
                                                        None)
            userInfo['community']['artists'] = soup.findAll('li')[12]['title']

            return userInfo

        def torrentInfo(self, dom, id):
            """
                Parse a torrent's page and returns a dictionnary with its information
            """
            torrentInfo = {'torrent':{}}
            torrentfiles = []
            torrentdescription = ""
            isreported = False
            isfreeleech = False
            soup = BeautifulSoup(str(dom))
            groupidurl = soup.findAll('div', {'class':'linkbox'})[0].find('a')['href']
            torrentInfo['torrent']['parentid'] = groupidurl[groupidurl.rfind("=")+1:]
            torrentInfo['torrent']['downloadurl'] = soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('a',{'title':'Download'})[0]['href']
            #is freeleech or/and reported?
            #both
            if len(soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('a')[-1].contents) == 4:
                isreported = True
                isfreeleech = True
                torrentInfo['torrent']['details'] = soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('a')[-1].contents[0].string[8:]
            #either
            elif len(soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('a')[-1].contents) == 2:
                if soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('a')[-1].contents[1].string == 'Reported':
                    isreported = True
                elif soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('a')[-1].contents[1].string == 'Freeleech!':
                    isreported = True
                torrentInfo['torrent']['details'] = soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('a')[-1].contents[0].string[8:]
            #none
            else:
                torrentInfo['torrent']['details'] = soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('a')[-1].string[8:]
            torrentInfo['torrent']['isfreeleech'] = isfreeleech
            torrentInfo['torrent']['isreported'] = isreported
            torrentInfo['torrent']['size'] = soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('td')[1].string
            torrentInfo['torrent']['snatched'] = soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('td')[2].string
            torrentInfo['torrent']['seeders'] = soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('td')[3].string
            torrentInfo['torrent']['leechers'] = soup.findAll('tr',{'id':'torrent%s'%id})[0].findAll('td')[4].string
            torrentInfo['torrent']['uploadedby'] = soup.findAll('tr',{'id':'torrent_%s'%id})[0].findAll('a')[0].string
            foldername = soup.findAll('div',{'id':'files_%s'%id})[0].findAll('div')[1].string
            torrentInfo['torrent']['foldername'] = self.utils.decodeHTMLEntities(foldername)
            files = soup.findAll('div',{'id':'files_%s'%id})[0].findAll('tr')
            for file in files[1:-1]:
                torrentfiles.append(self.utils.decodeHTMLEntities(file.contents[0].string))
            torrentInfo['torrent']['filelist'] = torrentfiles
            #is there any description?
            if len(soup.findAll('tr',{'id':'torrent_%s'%id})[0].findAll('blockquote')) > 1:
                description = torrentInfo['torrent']['description'] = soup.findAll('tr',{'id':'torrent_%s'%id})[0].findAll('blockquote')[1].contents
                info = ''
                for content in description:
                    if content.string:
                        info = "%s%s" % (info, self.utils._string(content.string))
                        torrentdescription = "%s%s" % (torrentdescription, self.utils._string(content.string))
            torrentInfo['torrent']['torrentdescription'] = torrentdescription

            return torrentInfo

        def artistInfo(self, dom):
            """
                Parse an artist's page and returns a dictionnary with its information
            """
            artistInfo = {}
            releases = []
            requests = []
            infoartist = ""
            tagsartist = []
            similarartists = []
            soup = BeautifulSoup(str(dom))
            for releasetype in soup.fetch('table',{'class':'torrent_table'}):
                releasetypenames = releasetype.findAll('strong')
                releasetypename = releasetype.findAll('strong')[0].string
                for release in releasetypenames[1:-1]:
                    #skip release edition info and Freeleech! <strong>s
                    if len(release.parent.contents) > 1 and len(release.contents) > 1 :
                        releaseyear = release.contents[0][0:4]
                        releasename = release.contents[1].string
                        releasehref = release.contents[1]['href']
                        releaseid = releasehref[releasehref.rfind('=')+1:]
                        releases.append({'releasetype':releasetypename,\
                         'year': releaseyear,'name':self.utils.decodeHTMLEntities(releasename),'id':releaseid})

            artistInfo['releases'] = releases
            #is there an artist image?
            artistInfo['image'] = None
            if soup.find('div', {'class':'box'}).find('img'):
                artistInfo['image'] = soup.find('div', {'class':'box'}).find('img')['src']
            #is there any artist info?
            contents = soup.find('div', {'class':'body'}).contents
            if len(contents) > 0:
                for content in contents:
                    if content.string:
                        infoartist = "%s%s" % (infoartist, self.utils._string(content.string))
            artistInfo['info'] = self.utils.decodeHTMLEntities(infoartist)
            #is there any artist tags?
            if soup.findAll('ul',{'class':'stats nobullet'})[0].findAll('li'):
                ul = soup.findAll('ul',{'class':'stats nobullet'})[0].findAll('li')
                for li in ul:
                    if li.contents[0].string:
                        tagsartist.append(self.utils._string(li.contents[0].string))
            artistInfo['tags'] = tagsartist
            #is there any similar artist?
            if soup.findAll('ul',{'class':'stats nobullet'})[2].findAll('span',{'title':'2'}):
                artists = soup.findAll('ul',{'class':'stats nobullet'})[2].findAll('span',{'title':'2'})
                for artist in artists:
                    if artist.contents[0].string:
                        similarartists.append(self.utils._string(artist.contents[0].string))
            artistInfo['similarartists'] = similarartists
            #is there any request?
            if soup.find('table',{'id':'requests'}):
                for request in soup.find('table',{'id':'requests'}).findAll('tr',{'class':re.compile('row')}):
                    requests.append({'requestname':request.findAll('a')[1].string,'id':request.findAll('a')[1]['href'][28:]})

            artistInfo['requests'] = requests

            return artistInfo

        def torrentsList(self,dom):
            """
                Parse a torrent's list page and returns a dictionnary with its information
            """
            torrentslist = []
            torrentssoup = dom.find("table", {"width": "100%"})
            pages = 0
            #if there's at least 1 torrent in the list
            if torrentssoup:
                navsoup = dom.find("div", {"class": "linkbox"})
                #is there a page navigation bar?
                if navsoup.contents:
                    #if there's more than 1 page of torrents
                    lastpage = navsoup.contents[-1]['href']
                    pages = lastpage[18:lastpage.find('&')]
                else:
                    #there's only one page
                    pages = 1
                #fetch all tr except first one (column head)
                for torrent in torrentssoup.fetch('tr')[1:]:
                    #exclude non music torrents
                    if torrent.find('td').find('div')['class'][0:10] == 'cats_music':
                        #workaround to check artist field content, crazy
                        if len(torrent.findAll('td')[1].find('span').parent.contents) == 11:
                            #one artist
                            torrentartist = (self.utils.decodeHTMLEntities(torrent.findAll('td')[1].find('span').nextSibling.nextSibling.string),)
                            artistid = (torrent.findAll('td')[1].find('span').nextSibling.nextSibling['href'][14:],)
                            torrentalbum = torrent.findAll('td')[1].find('span').nextSibling.nextSibling.nextSibling.nextSibling.string
                        elif len(torrent.findAll('td')[1].find('span').parent.contents) == 9:
                            #various artists
                            torrentartist = ('Various Artists',)
                            artistid = ()
                            torrentalbum = torrent.findAll('td')[1].find('span').nextSibling.nextSibling.string
                        elif len(torrent.findAll('td')[1].find('span').parent.contents) == 13:
                            #two artists
                            torrentartist = (self.utils.decodeHTMLEntities(torrent.findAll('td')[1].find('span').nextSibling.nextSibling.string), \
                                self.utils.decodeHTMLEntities(torrent.findAll('td')[1].find('span').nextSibling.nextSibling.nextSibling.nextSibling.string))
                            artistid = (torrent.findAll('td')[1].find('span').nextSibling.nextSibling['href'][14:],\
                                torrent.findAll('td')[1].find('span').nextSibling.nextSibling.nextSibling.nextSibling['href'][14:])
                            torrentalbum = torrent.findAll('td')[1].find('span').nextSibling.nextSibling.nextSibling.nextSibling.nextSibling.nextSibling.string
                        torrenttag = torrent.find('td').contents[1]['title']
                        torrentdl = torrent.findAll('td')[1].find('span').findAll('a')[0]['href']
                        torrentrm = torrent.findAll('td')[1].find('span').findAll('a')[1]['href']
                        torrentid = torrentrm[torrentrm.rfind('=')+1:]
                        torrentslist.append({'tag':torrenttag,\
                                            'dlurl':torrentdl,\
                                            'id':torrentid, \
                                            'artist':torrentartist,\
                                            'artistid':artistid,\
                                            'album':self.utils.decodeHTMLEntities(torrentalbum),'pages':pages})

            return torrentslist

        def whatForm(self, dom, action):
            """
                Parse a what.cd edit page and returns a dict with all form inputs/textareas names and values
                # Parameters:
                    * dom str: the edit page dom.
                    + action str: the action value from the requested form
            """
            inputs = {}

            form = dom.find('input',{'name':'action','value':action}).parent
            elements = form.fetch(('input','textarea'))
            #get all form elements except for submit input
            for element in elements[0:-1]:
                name = element.get('name',None)
                if element.name == 'textarea':
                    inputs[name] = element.string
                else:
                    inputs[name] = element.get('value',None)
            return inputs



if __name__ == "__main__":
	print "Module to manage what.cd as a web service"
