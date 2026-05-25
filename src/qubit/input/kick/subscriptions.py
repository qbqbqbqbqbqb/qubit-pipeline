"""
Kick subscriptions placeholder.

We currently use the public Pusher WebSocket for all real-time events
(chat, follows, subs, raids). No separate webhook/EventSub registration
is performed.

If you later want to add official webhook support, this file is where the
subscription logic would live.
"""
