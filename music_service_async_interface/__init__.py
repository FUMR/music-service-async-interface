__version__ = '0.1.0'

# TODO [#1]: Cover
#   abstract Cover.get_url()
#   abstract async Cover.get_async_file()

# TODO [#2]: Track
#   abstract async Track.get_stream_url
#   implemented async Track.get_async_file (basing on get_stream_url)
#   abstract async Track.get_metadata()

# TODO [#3]: TrackCollection
#   abstract gen TrackCollection.tracks()

# TODO [#4]: MusicServiceObject
#   abstract MusicServiceObject::from_url()
#   abstract MusicServiceObject::parse_urls()
#   abstract MusicServiceObject.get_url()

# TODO [#5]: Specify how to resolve collections of collections of tracks
#   eg. user containing playlists containing tracks or artist containing albums containing tracks
