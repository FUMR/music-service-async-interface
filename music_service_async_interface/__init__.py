__version__ = '0.1.0'

from abc import ABC, abstractmethod
from typing import Optional, Type, AsyncGenerator, Dict

import aiohttp

try:
    from httpseekablefile import AsyncSeekableHTTPFile
except ImportError:
    AsyncSeekableHTTPFile = None


# TODO [#5]: Specify how to resolve collections of collections of tracks
#   eg. user containing playlists containing tracks or artist containing albums containing tracks

# TODO [$5f4daa0c13741d00080a6c3e]: AudioQuality abstract class extending enum with comparability by definition order
#   https://docs.python.org/3/library/enum.html#using-a-custom-new
#   https://docs.python.org/3/library/enum.html#orderedenum
#   hold definition order as additional prop


class InvalidURL(Exception):
    pass


class Session(ABC):
    sess: aiohttp.ClientSession
    obj: Type['Object']

    async def object_from_url(self, url: str) -> 'Object':
        for child_cls in self.obj.__subclasses__():
            try:
                return await child_cls.from_url(self, url)
            except (InvalidURL, NotImplemented):
                pass

        # If none objects match url, then the url must be invalid
        raise InvalidURL

    @staticmethod
    @abstractmethod
    def is_valid_url(url) -> bool:
        """
        Performs basic check if string looks like music service URL
        """
        ...

    async def parse_urls(self, long_string: str) -> AsyncGenerator['Object', None]:
        """
        Parses `long_string` including music service URLs to corresponding music service objects
        :param long_string: long string including URLs to music service objects
        :return: generator with music service objects
        """
        for word in long_string.split(' '):
            if self.is_valid_url(word):
                try:
                    yield await self.object_from_url(word)
                except InvalidURL:
                    pass
                break


class Object(ABC):
    sess: Session

    @classmethod
    @abstractmethod
    async def from_url(cls, sess: Session, url: str) -> 'Object':
        # may raise InvalidURL
        raise NotImplemented

    @abstractmethod
    async def get_url(self) -> str:
        ...


class Cover(ABC):
    sess: Session

    @abstractmethod
    def get_url(self, *args, **kwargs) -> str:
        ...

    if AsyncSeekableHTTPFile is not None:
        async def get_async_file(self, filename: Optional[str] = None, *args, **kwargs) -> AsyncSeekableHTTPFile:
            return await AsyncSeekableHTTPFile.create(self.get_url(*args, **kwargs), filename, self.sess.sess)


class Track(Object, ABC):
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
    async def get_file_url(self, *args, **kwargs) -> str:
        ...

    async def get_async_file(self, filename: Optional[str] = None, *args, **kwargs) -> AsyncSeekableHTTPFile:
        return await AsyncSeekableHTTPFile.create(
            await self.get_file_url(*args, **kwargs),
            self.title if filename is None else filename,
            self.sess.sess
        )


class TrackCollection(Object, ABC):
    @abstractmethod
    async def tracks(self) -> AsyncGenerator[Track, None]:
        ...
