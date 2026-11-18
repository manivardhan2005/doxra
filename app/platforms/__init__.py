"""Third-party platform integration adapters package."""

from app.platforms.base import BasePlatform
from app.platforms.telegram import TelegramPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.slack import SlackPlatform
from app.platforms.twitter import TwitterPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.linkedin import LinkedInPlatform

__all__ = [
    "BasePlatform",
    "TelegramPlatform",
    "DiscordPlatform",
    "SlackPlatform",
    "TwitterPlatform",
    "MastodonPlatform",
    "LinkedInPlatform",
]
