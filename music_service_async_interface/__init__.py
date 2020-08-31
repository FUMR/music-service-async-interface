__version__ = '0.1.0'

# TODO [$5f4d57e6cad27e0007ff2cc7]: Cover
#   abstract Cover.get_url()
#   abstract async Cover.get_async_file()

# TODO [$5f4d57e6cad27e0007ff2cc8]: Track
#   abstract async Track.get_stream_url
#   implemented async Track.get_async_file (basing on get_stream_url)
#   abstract async Track.get_metadata()

# TODO [$5f4d57e6cad27e0007ff2cc9]: TrackCollection
#   abstract gen TrackCollection.tracks()

# TODO [$5f4d57e6cad27e0007ff2cca]: MusicServiceObject
#   abstract MusicServiceObject::from_url()
#   abstract MusicServiceObject::parse_urls()
#   abstract MusicServiceObject.get_url()

# TODO [$5f4d57e6cad27e0007ff2ccb]: Specify how to resolve collections of collections of tracks
#   eg. user containing playlists containing tracks or artist containing albums containing tracks
