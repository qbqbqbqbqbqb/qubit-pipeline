from twitchAPI.type import AuthScope

bot_scopes = [
    AuthScope.CHAT_READ,
    AuthScope.CHAT_EDIT
]

streamer_scopes = [
    AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
    AuthScope.CHANNEL_MANAGE_RAIDS
]

MAX_NEW_TOKENS_FOR_DIALOGUE_GENERATION = 30
MAX_GENERATION_ATTEMPTS = 3