


from AxiomMusic.core.bot import Axiomm
from AxiomMusic.core.dir import dirr
from AxiomMusic.core.git import git
from AxiomMusic.core.userbot import Userbot
from AxiomMusic.misc import dbb, heroku

from .logging import LOGGER

dirr()
#git()
dbb()
heroku()

app = Axiomm()
userbot = Userbot()


from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
