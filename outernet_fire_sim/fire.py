#!/usr/bin/env python3

# ORIGINAL CHATROOM TAKEN FROM https://github.com/michael-lazar/jetforce/blob/master/examples/chatroom.py

from __future__ import annotations

import random
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from inspect import cleandoc
from typing import Callable, ClassVar, Optional

from humanfriendly import format_timespan
from jetforce import GeminiServer, JetforceApplication, Response, Status
from pluralizer import Pluralizer
from twisted.internet import reactor, task
from twisted.internet.defer import AlreadyCalledError, Deferred

plural = Pluralizer().plural

# TODO: Fire dancers

ITEMS = [
    "Peach",
    "Banana",
    "Orange",
    "Marshmallow",
    "Teddy Bear",
    "Plastic",
    "Squirrel",
]


# emojis removed for now 🔥火🪵
def gen_fire_level(level):
    return "".join(random.choice("/\-=+|") for _ in range(level * 2))


class MessageQueue:
    def __init__(self, filename):
        self.listeners = []

        # Keep the most recent 100 messages in memory for efficiency, and
        # persist *all* messages to a plain text file.
        self.history_log = deque(maxlen=100)
        self.filename = filename
        self.load_history()

    def load_history(self):
        try:
            with open(self.filename) as fp:
                for line in fp:
                    self.history_log.append(line)
        except OSError:
            pass

    def update_history(self, message):
        self.history_log.append(message)
        with open(self.filename, "a") as fp:
            fp.write(message)

    def publish(self, message):
        message = f"[{datetime.utcnow():%Y-%m-%dT%H:%M:%SZ}] {message}\n"
        self.update_history(message)

        # Stream the message to all open client connections
        listeners = self.listeners
        self.listeners = []
        for listener in listeners:
            try:
                listener.callback(message)
            except AlreadyCalledError:
                # The connection has disconnected, ignore it
                pass

    def subscribe(self):
        # Register a deferred response that will trigger whenever the next
        # message is published to the queue
        d = Deferred()
        self.listeners.append(d)
        return d


queue = MessageQueue("/tmp/orpheus_fire_chat.txt")

app = JetforceApplication()


@dataclass
class Fire:
    fire: deque[str] = field(
        default_factory=lambda: deque(gen_fire_level(i) for i in range(1, 5))
    )
    level: int = 4
    items: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=lambda: {})
    dead: bool = False
    cooked_items: dict = field(
        default_factory=lambda: {k: 0 if k != "Log" else -1 for k in (ITEMS + ["Log"])}
    )
    reset_start: int = 0
    start_time: int = field(default_factory=lambda: int(time.time()))
    longest_time: ClassVar[int] = 0

    def add_item(self, question: str = "", affirmative: bool = False):
        def callback(adder):
            @app.route(f"/{adder.__name__}")
            def add_request(request):
                if question and not request.query:
                    return Response(Status.INPUT, question)
                item_name = (
                    request.query
                    if request.query and not affirmative
                    else adder.__name__.replace("_", " ")
                ).lower()
                affirmative_answer = request.query and request.query[0].lower() == "y"
                # sus
                if not affirmative or (affirmative_answer and request.query[0].lower() == "y"):
                    self.items.append(item_name.title())
                if (item := adder(item_name if not affirmative else affirmative_answer)) is not None:
                    reactor.callLater(20, lambda: self.cook_item(item_name))
                    self.add(item)
                return Response(Status.REDIRECT_TEMPORARY, "/")

        return callback

    def cook_item(self, item):
        self.cooked_items[item.title()] += 1
        self.items.pop()
        self.fire.popleft()


    def display_stats(self) -> str:
        item_stat_dict = {k: 0 for k in ITEMS}
        item_stat_dict["Log"] = self.level  # hack
        item_stat_dict.update(Counter(self.items))
        item_stats = "\n".join(
            f"{plural(stat)}: {item}" for stat, item in item_stat_dict.items()
        )
        cooked_stats = "\n".join(
            f"{plural(stat)}: {item}" for stat, item in self.cooked_items.items() if stat != "Log"
        )
        stat_stats = "\n".join(f"{stat}: {item}" for stat, item in self.stats.items())
        current_time = time.time() - self.start_time
        current_time_msg = f"The fire has been burning for {format_timespan(current_time)}"
        if current_time >= self.longest_time:
            time_record_msg = "This is the longest time on record!"
            self.longest_time = current_time
        else:
            time_record_msg = "The longest time so far has been" f"{format_timespan(self.longest_time)}"
        return f"""### Time
{current_time_msg}
{time_record_msg}
### Burning 🔥: 
{item_stats}
{stat_stats}
### Cooked ☠:
{cooked_stats}

""".strip()

    def display_fire(self) -> str:
        try:
            pad_len = len(self.fire[-1])
        except IndexError:
            return ""
        return "\n".join(f"{item.center(pad_len, ' ')}" for item in self.fire)

    def decay(self):
        if self.items:
            self.items.pop()
        else:
            self.dec_level()

    def reset(self):
        self.__init__()

    def death_msg(self):
        if self.cooked_items["Squirrel"] >= 3:
            story = (
                "The squirrels were angry at y'all for eating them "
                "and called mama black bear to ravage Outernet. "
                "You are all dead."
            )
        elif self.cooked_items["Plastic"] >= 7:
            story = "The plastic fumes were too much for y'all. " "You are all dead."
        elif self.level == 0:
            story = "The fire has gone out. You go back to your wet tents in dissapointment."
        else:
            return None
        if not self.dead:
            reactor.callLater(30, self.reset)
            self.dead = True
            self.reset_start = time.time()
        story += f"\nOnly {format_timespan(30 - (time.time() - self.reset_start))} until the fire restarts."
        return story

    def page(self):
        msg = "# Outernet Fire Sim\n"
        if (death_msg := self.death_msg()) is not None:
            msg += death_msg
        else:
            msg += Rf"""Relive the bonfire experience! Reload to see the fire change.
Built with gemini, a text only HTTP/HTML alternative.
Install any gemini client and head to gemini://fire.outernet to join!
```Fire!
{self.display_fire()}
```
## Fire

=> /fruit
(roast a fruit on the fire)

=> /marshmallow
(cook a marshmallow on the fire)

=> /log 
(add a log to the fire)

=> /teddy_bear
(sacrifice a teddy bear to the fire)

=> /plastic 
(create some carciogens with the fire)

=> /squirrel 
(cook a squirrel on the fire)

=> /take
(take the top item from the fire)

## Stats
{self.display_stats()}

## Chat
=> /stream
(open a long-running TCP connection that will stream messages in real-time)

=> /submit
(open an input loop to submit messages to the room)

=> /history
(view the last 100 messages)"""
        return msg

    def add(self, item: str) -> None:
        self.fire.appendleft(item)

    def inc_level(self, amount=1) -> None:
        for _ in range(amount):
            self.level += 1
            self.fire.append(gen_fire_level(self.level))

    def dec_level(self, amount=1) -> None:
        for _ in range(amount):
            self.level -= 1
            self.cooked_items["Log"] += 1
            try:
                self.fire.pop()
            except IndexError:
                pass


fire = Fire()


@fire.add_item("Would you like to add a fruit to the fire? Peach, Banana, Orange, Grape, or Pineapple?")
def fruit(item: str):
    return {
        "peach": "🍑",
        "banana": "🍌",
        "orange": "🍊",
        "grape": "🍇",
        "pineapple": "🍍",
    }.get(item)


@app.route("/log")
def log(request):
    fire.inc_level(1)
    return Response(Status.REDIRECT_TEMPORARY, "/")


@fire.add_item()
def marshmallow(_):
    return "🍢"


@fire.add_item()
def teddy_bear(_):
    return "🧸"


@fire.add_item()
def plastic(_):
    return random.choice("🧴🪒")


@fire.add_item(
    "You monster. Do you really want to cook a cute squirrel? [yes/no]", True
)
def squirrel(item):
    return "🐿️" if item else None


@app.route("/take")
def take(request):
    try:
        fire.items.pop()
    except IndexError:
        return Response(Status.TEMPORARY_FAILURE, "Nothing to take")
    fire.fire.popleft()
    return Response(Status.REDIRECT_TEMPORARY, "/")


def get_username(request):
    if "REMOTE_USER" in request.environ:
        return request.environ["REMOTE_USER"]
    else:
        return request.environ["REMOTE_ADDR"]


@app.route("", strict_trailing_slash=False)
def index(request):
    return Response(Status.SUCCESS, "text/gemini", fire.page())


@app.route("/history")
def history(request):
    body = "".join(queue.history_log)
    return Response(Status.SUCCESS, "text/plain", body)


@app.route("/submit")
def submit(request):
    if request.query:
        message = f"<{get_username(request)}> {request.query}"
        queue.publish(message)
    return Response(Status.INPUT, "Enter Message:")


@app.route("/stream")
def stream(request):
    def on_disconnect(failure):
        queue.publish(f"*** {get_username(request)} disconnected")
        return failure

    def stream_forever():
        yield "Fire chat started...\n"
        while True:
            deferred = queue.subscribe()
            deferred.addErrback(on_disconnect)
            yield deferred

    queue.publish(f"*** {get_username(request)} joined")
    return Response(Status.SUCCESS, "text/plain", stream_forever())


loop = task.LoopingCall(fire.decay)
loop.start(270)

if __name__ == "__main__":
    server = GeminiServer(
        app,
        host="0.0.0.0",
        # hostname="fire.outernet",
        # certfile="fire.outernet.crt",
        # keyfile="fire.outernet.key",
    )
    server.run()
