__version__ = "0.1.0"

import enum
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import AsyncGenerator, Dict, Optional, Set, Type

import aiohttp

try:
    from httpseekablefile import AsyncSeekableHTTPFile
except ImportError:
    AsyncSeekableHTTPFile = None


def plural_noun(val):
    # TODO: Plural noun rules
    #   https://www.grammarly.com/blog/plural-nouns/
    return val + "s"


class InvalidURL(Exception):
    pass


class InsufficientAudioQuality(Exception):
    pass


class AudioQuality(enum.Enum):
    """Comparable enum for definition of track's audio quality.

    Qualities are sorted in order of definition.
    First defined is lower quality than second defined.

    Simple example:
    >>> class TestAudioQuality(AudioQuality):
    >>>     LOW = 'low'
    >>>     MEDIUM = 'med'
    >>>     HIGH = 'high'
    >>>
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
        return self._preferred_audio_quality

    @preferred_audio_quality.setter
    def preferred_audio_quality(self, quality: AudioQuality):
        if not isinstance(quality, self._quality):
            raise TypeError(f"quality must be instance of {self._quality}")
        self._preferred_audio_quality = quality

    @property
    def required_audio_quality(self) -> AudioQuality:
        return self._required_audio_quality

    @required_audio_quality.setter
    def required_audio_quality(self, quality: AudioQuality):
        if not isinstance(quality, self._quality):
            raise TypeError(f"quality must be instance of {self._quality}")
        self._required_audio_quality = quality

    async def object_from_url(self, url: str) -> "Object":
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
        """Performs basic check if string looks like music service URL"""
        ...

    async def parse_urls(self, long_string: str) -> AsyncGenerator["Object", None]:
        """Parses `long_string` including music service URLs to corresponding music service objects

        :param long_string: long string including URLs to music service objects
        :return: generator with music service objects
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


class Object(ABC):
    sess: Session

    @classmethod
    @abstractmethod
    async def from_url(cls, sess: Session, url: str) -> "Object":
        """
        :raises: `InvalidURL` -- when URL is being unparsable by this `Object`
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def from_id(cls, sess: Session, id_) -> "Object":
        ...

    @abstractmethod
    async def get_url(self) -> str:
        ...

    @abstractmethod
    def get_id(self):
        ...


class Cover(ABC):
    sess: Session

    @abstractmethod
    def get_url(self, *args, **kwargs) -> str:
        ...

    if AsyncSeekableHTTPFile is not None:

        async def get_async_file(self, filename: Optional[str] = None, *args, **kwargs) -> AsyncSeekableHTTPFile:
            return await AsyncSeekableHTTPFile.create(
                self.get_url(*args, **kwargs),
                filename,
                self.sess.sess,
            )


class Track(Object, ABC):
    # TODO [#7]: Consider adding audio_quality property to Track

    @property
    @abstractmethod
    def title(self) -> str:
        ...

    @property
    @abstractmethod
    def artist_name(self) -> str:
        ...

    @abstractmethod
    async def get_metadata(self) -> Dict[str, str]:
        """
        :return: dict containing tags to be directly written on file when doing metadata tagging
        """
        ...

    @abstractmethod
    async def get_file_url(
        self,
        required_quality: Optional[AudioQuality] = None,
        preferred_quality: Optional[AudioQuality] = None,
        **kwargs,
    ) -> str:
        """This method asks service for music file url

        :param required_quality: Quality requirement for track
        :param preferred_quality: Preferred audio quality, which we are asking for
        :raise: :class:`InsufficientAudioQuality` when quality requirements are not met
        :return: Music file URL
        """
        ...

    if AsyncSeekableHTTPFile is not None:

        async def get_async_file(
            self,
            required_quality: Optional[AudioQuality] = None,
            preferred_quality: Optional[AudioQuality] = None,
            filename: Optional[str] = None,
            **kwargs,
        ) -> AsyncSeekableHTTPFile:
            """Gets async `filelike` object for Track

            :param required_quality: Quality requirement for track
            :param preferred_quality: Preferred audio quality, which we are asking for
            :param filename: File name for `filelike`
            :raise: :class:`InsufficientAudioQuality` when quality requirements are not met
            :return: Music file
            """

            return await AsyncSeekableHTTPFile.create(
                await self.get_file_url(required_quality, preferred_quality, **kwargs),
                self.title if filename is None else filename,
                self.sess.sess,
            )


class ObjectCollection:
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

            def iter(self, collection_type_: Type[Object]) -> AsyncGenerator[Object, None]:
                if collection_type_ in self.collection_of:
                    func_name_ = plural_noun(collection_type_.__name__.lower())
                    return getattr(self, func_name_)()
                raise KeyError(collection_type_)

        async def _load_collections(self) -> AsyncGenerator[Object, None]:
            ...

        func_name = plural_noun(collection_type.__name__.lower())
        _load_collections.__name__ = func_name

        return type(
            f"ObjectCollection[{collection_type.__name__}]",
            (Object, CollectionHelper, ABC),
            {"__module__": cls.__module__, func_name: abstractmethod(_load_collections)},
        )
