__version__ = "0.1.0"

import enum
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import AsyncGenerator, Dict, List, Optional, Set, Type, Union

import aiohttp

try:
    from httpseekablefile import AsyncSeekableHTTPFile
except ImportError:
    AsyncSeekableHTTPFile = None


def plural_noun(val):
    # TODO [#26]: Plural noun rules
    #   https://www.grammarly.com/blog/plural-nouns/
    return val + "s"


class InvalidURL(Exception):
    pass


class InsufficientAudioQuality(Exception):
    pass


class InvalidSearchType(Exception):
    pass


class AudioQuality(enum.Enum):
    """Comparable enum for definition of track's audio quality

    Qualities are sorted in order of definition.
    First defined is lower quality than second defined.

    Simple example:
    >>> class TestAudioQuality(AudioQuality):
    ...     LOW = 'low'
    ...     MEDIUM = 'med'
    ...     HIGH = 'high'
    ...
    >>> TestAudioQuality.LOW > TestAudioQuality.HIGH
    False
    >>> TestAudioQuality.LOW >= TestAudioQuality.HIGH
    False
    >>> TestAudioQuality.LOW < TestAudioQuality.HIGH
    True
    >>> TestAudioQuality.LOW <= TestAudioQuality.HIGH
    True
    >>> TestAudioQuality.MEDIUM > TestAudioQuality.LOW
    True
    >>> TestAudioQuality.MEDIUM > TestAudioQuality.HIGH
    False
    >>> TestAudioQuality.MEDIUM < TestAudioQuality.HIGH
    False
    """

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self._member_names_.index(self.name) >= self._member_names_.index(other.name)
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self._member_names_.index(self.name) > self._member_names_.index(other.name)
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self._member_names_.index(self.name) <= self._member_names_.index(other.name)
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self._member_names_.index(self.name) < self._member_names_.index(other.name)
        return NotImplemented


class Session(ABC):
    """Main abstract class holding session and other data neccessary to interact with the music service

    Starting point of the library.
    Can be used for storing auth or other data.
    Inheriting class should fill `_obj` and `_quality` with classes extending :class:`Object` and
    :class:`AudioQuality` respectively.

    example:
    >>> class TestObject(Object, ABC):
    ...     ...
    ...
    >>> class TestAudioQuality(AudioQuality):
    ...     LOW = 'low'
    ...     MEDIUM = 'med'
    ...     HIGH = 'high'
    ...
    >>> class TestSession(Session):
    ...     _obj = TestObject
    ...     _quality = TestAudioQuality
    ...     ...
    ...
    """

    sess: aiohttp.ClientSession
    _obj: Type["Object"]
    _quality: Type[AudioQuality]

    @abstractmethod
    def __init__(self, sess: Optional[aiohttp.ClientSession] = None):
        if not hasattr(self.__class__, "_obj"):
            raise TypeError(f"Can't instantiate abstract class {self.__class__} with abstract property _obj")
        if not hasattr(self.__class__, "_quality"):
            raise TypeError(f"Can't instantiate abstract class {self.__class__} with abstract property _quality")

        self.sess = aiohttp.ClientSession() if sess is None else sess
        self._required_audio_quality: AudioQuality = min(self._quality)
        self._preferred_audio_quality: AudioQuality = max(self._quality)

    @property
    def preferred_audio_quality(self) -> AudioQuality:
        """Preferred (upper limit) :class:`AudioQuality` for tracks downloaded using this session
        Can be overridden when downloading track, this is a default value.

        :return: preferred :class:`AudioQuality`
        """
        return self._preferred_audio_quality

    @preferred_audio_quality.setter
    def preferred_audio_quality(self, quality: AudioQuality):
        if not isinstance(quality, self._quality):
            raise TypeError(f"quality must be instance of {self._quality}")
        self._preferred_audio_quality = quality

    @property
    def required_audio_quality(self) -> AudioQuality:
        """Required (lower limit) :class:`AudioQuality` for tracks downloaded using this session
        Can be overridden when downloading track, this is a default value.

        :return: required :class:`AudioQuality`
        """
        return self._required_audio_quality

    @required_audio_quality.setter
    def required_audio_quality(self, quality: AudioQuality):
        if not isinstance(quality, self._quality):
            raise TypeError(f"quality must be instance of {self._quality}")
        self._required_audio_quality = quality

    async def object_from_url(self, url: str) -> "Object":
        """Fetches an object from the music service
        Automatically creates appropriate :class:`Object` type based on provided URL, e.g. Track, Playlist.

        example:
        >>> await sess.object_from_url('https://www.tidal.com/artist/17752')
        <tidal_async.api.Artist (17752): Psychostick>

        :param url: music service URL pointing to object
        :raises InvalidURL: when URL is being unparsable by music service
        :return: corresponding :class:`Object`, e.g. :class:`Track`
        """
        for child_cls in self._obj.__subclasses__():
            try:
                return await child_cls.from_url(self, url)
            except (InvalidURL, NotImplementedError):
                pass

        # If none objects match url, then the url must be invalid
        raise InvalidURL

    @staticmethod
    @abstractmethod
    def is_valid_url(url) -> bool:
        """Performs basic check if string looks like music service URL

        :param url: URL to check
        """
        ...

    async def parse_urls(self, long_string: str) -> AsyncGenerator["Object", None]:
        """Parses `long_string` including music service URLs to corresponding music service objects

        example:
        >>> [o async for o in sess.parse_urls('''parsing https://www.tidal.com/artist/17752 topkek
        ... https://www.tidal.com/album/91969976 urls''')]
        [<tidal_async.api.Artist (17752): Psychostick>, <tidal_async.api.Album (91969976): Do>]

        :param long_string: long string including URLs to music service objects
        :yield: music service objects for found URLs
        """
        # TODO [#17]: How should we handle exceptions on loading each URL in Session.parse_urls?
        #   What if for example one of URLs is invalid?
        #   ATM it would crash whole function and not parse any other URL

        for word in long_string.split():
            if self.is_valid_url(word):
                try:
                    yield await self.object_from_url(word)
                except InvalidURL:
                    pass

    @abstractmethod
    async def search(
        self, query: str, types: Optional[Union[Type["Searchable"], List[Type["Searchable"]]]] = None, limit: int = 10
    ) -> AsyncGenerator["Searchable", None]:
        """Searches music service for specific :class:`Searchable` types using `query`
        Accepts single :class:`Searchable` type, list of them or allows to entirely skip `types` parameter.

        :param query: search string/phrase
        :param types: :class:`Searchable` type or list of types, restricts search results to this type,
        e.g. if you want to search for tracks use `sess.search('text', Track)`
        or if you want to search for albums and playlists use `sess.search('text', [Album, Playlist])`.
        Also allows to search for all possible objects, then this parameter is left unset, set to None or an empty list.
        :param limit: amount of records to search for
        :raise InvalidSearchType: when `types` contains invalid type (not a subclass of :class:`Searchable`)
        :yield: :class:`Searchable` objects for each search result
        """
        ...


class Object(ABC):
    """Abstract class representing music service object e.g. Track, Artist or Playlist
    Should be subclassed on API implementation of music service.
    """

    sess: Session

    @classmethod
    @abstractmethod
    async def from_url(cls, sess: Session, url: str) -> "Object":
        """Fetches corresponding object from music service based on URL

        :param sess: :class:`Session` instance to use when loading data from music service
        :param url: music service URL pointing to object
        :raises NotImplementedError: when particular object type can't be fetched by URL
        :raises InvalidURL: when URL is being unparsable by this :class:`Object`
        :return: corresponding object, e.g. :class:`Track` or :class:`Playlist`
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def from_id(cls, sess: Session, id_) -> "Object":
        """Fetches corresponding object from music service based on ID

        :param sess: :class:`Session` instance to use when loading data from music service
        :param id_: ID of :class:`Object` provided by the music service
        :return: corresponding :class:`Object`
        """
        ...

    @abstractmethod
    async def get_url(self) -> str:
        """Gets object's URL

        :return: URL to object
        """
        ...

    @abstractmethod
    def get_id(self):
        """Gets object's music service ID

        :return: ID of :class:`Object` provided by the music service
        """
        ...

    @property
    @abstractmethod
    def cover(self) -> Optional["Cover"]:
        """
        :return: :class:`Cover` image or `None` if :class:`Object` has no cover
        """
        ...


class Searchable(Object, ABC):
    """Generic class to be extended by any searchable :class:`Object`
    For example if music service is able to search for tracks and
    playlists, `Track` and `Playlist` classes should extend this class.
    """


class Cover(ABC):
    sess: Session

    @abstractmethod
    def get_url(self, *args, **kwargs) -> str:
        """Gets :class:`Cover` image URL

        :param args: allows overriding function to define custom positional arguments
        :param kwargs: allows overriding function to define custom keyword arguments
        :return: URL to :class:`Cover` image
        """
        ...

    async def get_async_file(self, filename: Optional[str] = None, *args, **kwargs) -> AsyncSeekableHTTPFile:
        """Gets async `filelike` object containing cover art

        :param args: allows subfunction to define custom positional arguments
        :param kwargs: allows subfunction to define custom keyword arguments
        :param filename: filename for `filelike` object
        :raises ImportError: when `httpseekablefile` library is not installed
        :return: async `filelike` with coverart
        """
        if AsyncSeekableHTTPFile is None:
            raise ImportError("httpseekablefile not installed")

        return await AsyncSeekableHTTPFile.create(
            self.get_url(*args, **kwargs),
            filename,
            self.sess.sess,
        )


class Track(Object, ABC):
    @property
    @abstractmethod
    def title(self) -> str:
        """
        :return: :class:`Track`'s title
        """
        ...

    @property
    @abstractmethod
    def artist_name(self) -> str:
        """
        :return: :class:`Track`'s artist's name
        """
        ...

    @abstractmethod
    async def get_metadata(self) -> Dict[str, str]:
        """Generates metadata for music file to be tagged with

        :return: dict containing tags compatbile with `mediafile` library
        """
        ...

    @abstractmethod
    async def get_file_url(
        self,
        required_quality: Optional[AudioQuality] = None,
        preferred_quality: Optional[AudioQuality] = None,
        **kwargs,
    ) -> str:
        """Fetches direct URL to music file from music service

        :param required_quality: required (lower limit) :class:`AudioQuality` for track
        if ommited value from session is used
        :param preferred_quality: preferred (upper limit) :class:`AudioQuality` you want to get
        if ommited value from session is used
        :param kwargs: allows subfunction to define custom keyword arguments
        :raises InsufficientAudioQuality: when available :class:`AudioQuality` is lower than `required_quality`
        :return: direct URL of music file
        """
        ...

    async def get_async_file(
        self,
        required_quality: Optional[AudioQuality] = None,
        preferred_quality: Optional[AudioQuality] = None,
        filename: Optional[str] = None,
        **kwargs,
    ) -> AsyncSeekableHTTPFile:
        """Gets async `filelike` object containing track file

        :param required_quality: required (lower limit) :class:`AudioQuality` for track
        if ommited value from session is used
        :param preferred_quality: preferred (upper limit) :class:`AudioQuality` you want to get
        if ommited value from session is used
        :param filename: filename for `filelike` object
        :param kwargs: allows subfunction to define custom keyword arguments
        :raises ImportError: when `httpseekablefile` library is not installed
        :raises InsufficientAudioQuality: when available :class:`AudioQuality` is lower than `required_quality`
        :return: async `filelike` with music file
        """
        if AsyncSeekableHTTPFile is None:
            raise ImportError("httpseekablefile not installed")

        return await AsyncSeekableHTTPFile.create(
            await self.get_file_url(required_quality, preferred_quality, **kwargs),
            self.title if filename is None else filename,
            self.sess.sess,
        )


class ObjectCollection:
    """Base class for any collections of objects

    Makes sure particular method for object type is overridden.
    Allows easy iteration over all object types in collection.

    example:
    >>> class Album(ObjectCollection[Track]):
    ...     from_id = from_url = get_id = get_url = cover = lambda *a, **b: None
    ...     async def tracks(self):
    ...         for i in range(5):
    ...             yield f"Track {i}"
    ...
    >>> album = Album()
    >>> album
    <__main__.Album at 0x7f38605b6eb0>

    **You cannot create `ObjectCollection[Track]` subclass without method `tracks()`.**
    Way of creating method names are defined by `plural_noun(obj_name)` function.

    Now you can iterate over collection two ways.
    Normal way - using programmer friendly method:
    >>> async for t in album.tracks():
    ...    print(t)
    ...
    Track 0
    Track 1
    Track 2
    Track 3
    Track 4

    `iter(collection_type_)` method - tree-based program friendly method:
    >>> async for t in album.iter(Track):
    ...     print(t)
    ...
    Track 0
    Track 1
    Track 2
    Track 3
    Track 4

    You can also check what types of objects are collected in the subclass:
    >>> album.collection_of
    {music_service_async_interface.Track}
    >>> Album.collection_of
    {music_service_async_interface.Track}

    more complicated example:
    >>> class Album(ObjectCollection[Track]):
    ...     from_id = from_url = get_id = get_url = cover = tracks = lambda *a, **b: None
    ...
    >>> class Playlist(ObjectCollection[Track]):
    ...     from_id = from_url = get_id = get_url = cover = tracks = lambda *a, **b: None
    ...
    >>> class Artist(ObjectCollection[Album], ObjectCollection[Playlist]):
    ...     from_id = from_url = get_id = get_url = cover = lambda *a, **b: None
    ...     async def albums(self):
    ...         for i in range(5):
    ...             yield f"Album {i}"
    ...     async def playlists(self):
    ...         for i in range(5):
    ...             yield f"Playlist {i}"
    ...
    >>> Artist.collection_of
    {__main__.Album, __main__.Playlist}
    >>> artist = Artist()
    >>> artist.collection_of
    {__main__.Album, __main__.Playlist}
    >>> async for i in artist.iter(Album):
    ...     print(i)
    ...
    Album 0
    Album 1
    Album 2
    Album 3
    Album 4
    >>> async for i in artist.albums():
    ...     print(i)
    ...
    Album 0
    Album 1
    Album 2
    Album 3
    Album 4
    >>> async for i in artist.iter(Playlist):
    ...     print(i)
    ...
    Playlist 0
    Playlist 1
    Playlist 2
    Playlist 3
    Playlist 4
    >>> async for i in artist.playlists():
    ...     print(i)
    ...
    Playlist 0
    Playlist 1
    Playlist 2
    Playlist 3
    Playlist 4
    """

    def __new__(cls):
        raise TypeError(f"Can't instantiate this class directly. Try {cls.__name__}[Object]")

    def __init_subclass__(cls):
        raise TypeError("Can't subclass this class directly. Try ObjectCollection[Object]")

    @classmethod
    @lru_cache
    def __class_getitem__(cls, collection_type: Type[Object]):
        if not issubclass(collection_type, Object):
            raise TypeError(f"index must be subclass of Object, not {collection_type}")

        class CollectionHelper:
            collection_of: Set[Type[Object]] = set()

            def __init_subclass__(cls, **kwargs):
                super().__init_subclass__(**kwargs)
                if cls.collection_of:
                    cls.collection_of.add(collection_type)
                else:
                    cls.collection_of = {collection_type}

            def iter(self, collection_type_: Type[Object], *args, **kwargs) -> AsyncGenerator[Object, None]:
                if collection_type_ in self.collection_of:
                    func_name_ = plural_noun(collection_type_.__name__.lower())
                    return getattr(self, func_name_)(*args, **kwargs)
                raise KeyError(collection_type_)

        async def _load_collections(self, *args, **kwargs) -> AsyncGenerator[Object, None]:
            ...

        _load_collections.__name__ = func_name = plural_noun(collection_type.__name__.lower())

        return type(
            f"ObjectCollection[{collection_type.__name__}]",
            (Object, CollectionHelper, ABC),
            {"__module__": cls.__module__, func_name: abstractmethod(_load_collections)},
        )
