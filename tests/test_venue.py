#!/usr/bin/env python
#
# A library that provides a Python interface to the Telegram Bot API
# Copyright (C) 2015-2022
# Leandro Toledo de Souza <devs@python-telegram-bot.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser Public License for more details.
#
# You should have received a copy of the GNU Lesser Public License
# along with this program.  If not, see [http://www.gnu.org/licenses/].
import asyncio

import pytest

from telegram import Location, Venue
from telegram.error import BadRequest
from telegram.request import RequestData


@pytest.fixture(scope="module")
def venue():
    return Venue(
        Space.location,
        Space.title,
        Space.address,
        foursquare_id=Space.foursquare_id,
        foursquare_type=Space.foursquare_type,
        google_place_id=Space.google_place_id,
        google_place_type=Space.google_place_type,
    )


class Space:
    location = Location(longitude=-46.788279, latitude=-23.691288)
    title = "title"
    address = "address"
    foursquare_id = "foursquare id"
    foursquare_type = "foursquare type"
    google_place_id = "google place id"
    google_place_type = "google place type"


class TestVenueNoReq:
    def test_slot_behaviour(self, venue, mro_slots):
        for attr in venue.__slots__:
            assert getattr(venue, attr, "err") != "err", f"got extra slot '{attr}'"
        assert len(mro_slots(venue)) == len(set(mro_slots(venue))), "duplicate slot"

    def test_de_json(self, bot):
        json_dict = {
            "location": Space.location.to_dict(),
            "title": Space.title,
            "address": Space.address,
            "foursquare_id": Space.foursquare_id,
            "foursquare_type": Space.foursquare_type,
            "google_place_id": Space.google_place_id,
            "google_place_type": Space.google_place_type,
        }
        venue = Venue.de_json(json_dict, bot)
        assert venue.api_kwargs == {}

        assert venue.location == Space.location
        assert venue.title == Space.title
        assert venue.address == Space.address
        assert venue.foursquare_id == Space.foursquare_id
        assert venue.foursquare_type == Space.foursquare_type
        assert venue.google_place_id == Space.google_place_id
        assert venue.google_place_type == Space.google_place_type

    async def test_send_with_venue(self, monkeypatch, bot, chat_id, venue):
        async def make_assertion(url, request_data: RequestData, *args, **kwargs):
            data = request_data.json_parameters
            return (
                data["longitude"] == str(Space.location.longitude)
                and data["latitude"] == str(Space.location.latitude)
                and data["title"] == Space.title
                and data["address"] == Space.address
                and data["foursquare_id"] == Space.foursquare_id
                and data["foursquare_type"] == Space.foursquare_type
                and data["google_place_id"] == Space.google_place_id
                and data["google_place_type"] == Space.google_place_type
            )

        monkeypatch.setattr(bot.request, "post", make_assertion)
        message = await bot.send_venue(chat_id, venue=venue)
        assert message

    async def test_send_venue_without_required(self, bot, chat_id):
        with pytest.raises(ValueError, match="Either venue or latitude, longitude, address and"):
            await bot.send_venue(chat_id=chat_id)

    async def test_send_venue_mutually_exclusive(self, bot, chat_id, venue):
        with pytest.raises(ValueError, match="Not both"):
            await bot.send_venue(
                chat_id=chat_id,
                latitude=1,
                longitude=1,
                address="address",
                title="title",
                venue=venue,
            )

    def test_to_dict(self, venue):
        venue_dict = venue.to_dict()

        assert isinstance(venue_dict, dict)
        assert venue_dict["location"] == venue.location.to_dict()
        assert venue_dict["title"] == venue.title
        assert venue_dict["address"] == venue.address
        assert venue_dict["foursquare_id"] == venue.foursquare_id
        assert venue_dict["foursquare_type"] == venue.foursquare_type
        assert venue_dict["google_place_id"] == venue.google_place_id
        assert venue_dict["google_place_type"] == venue.google_place_type

    def test_equality(self):
        a = Venue(Location(0, 0), Space.title, Space.address)
        b = Venue(Location(0, 0), Space.title, Space.address)
        c = Venue(Location(0, 0), Space.title, "")
        d = Venue(Location(0, 1), Space.title, Space.address)
        d2 = Venue(Location(0, 0), "", Space.address)

        assert a == b
        assert hash(a) == hash(b)
        assert a is not b

        assert a == c
        assert hash(a) == hash(c)

        assert a != d
        assert hash(a) != hash(d)

        assert a != d2
        assert hash(a) != hash(d2)


class TestVenueReq:
    @pytest.mark.parametrize(
        "default_bot,custom",
        [
            ({"allow_sending_without_reply": True}, None),
            ({"allow_sending_without_reply": False}, None),
            ({"allow_sending_without_reply": False}, True),
        ],
        indirect=["default_bot"],
    )
    async def test_send_venue_default_allow_sending_without_reply(
        self, default_bot, chat_id, venue, custom
    ):
        reply_to_message = await default_bot.send_message(chat_id, "test")
        await reply_to_message.delete()
        if custom is not None:
            message = await default_bot.send_venue(
                chat_id,
                venue=venue,
                allow_sending_without_reply=custom,
                reply_to_message_id=reply_to_message.message_id,
            )
            assert message.reply_to_message is None
        elif default_bot.defaults.allow_sending_without_reply:
            message = await default_bot.send_venue(
                chat_id, venue=venue, reply_to_message_id=reply_to_message.message_id
            )
            assert message.reply_to_message is None
        else:
            with pytest.raises(BadRequest, match="message not found"):
                await default_bot.send_venue(
                    chat_id, venue=venue, reply_to_message_id=reply_to_message.message_id
                )

    @pytest.mark.parametrize("default_bot", [{"protect_content": True}], indirect=True)
    async def test_send_venue_default_protect_content(self, default_bot, chat_id, venue):
        tasks = asyncio.gather(
            default_bot.send_venue(chat_id, venue=venue),
            default_bot.send_venue(chat_id, venue=venue, protect_content=False),
        )
        protected, unprotected = await tasks
        assert protected.has_protected_content
        assert not unprotected.has_protected_content
