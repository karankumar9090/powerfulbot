#!/usr/bin/env python
#
# A library that provides a Python interface to the Telegram Bot API
# Copyright (C) 2015-2023
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
import inspect
import os
from typing import List

import httpx
import pytest
from bs4 import BeautifulSoup

import telegram
from telegram._utils.defaultvalue import DefaultValue
from tests.auxil.envvars import env_var_2_bool

IGNORED_OBJECTS = ("ResponseParameters", "CallbackGame")
IGNORED_PARAMETERS = {
    "self",
    "args",
    "read_timeout",
    "write_timeout",
    "connect_timeout",
    "pool_timeout",
    "bot",
    "api_kwargs",
    "thumb",  # was renamed to "thumbnail" in Bot API 6.6 in a lot of classes and methods
    "thumb_url",  # was renamed to "thumbnail_url" in Bot API 6.6 in a lot of classes
}

ignored_param_requirements = {  # Ignore these since there's convenience params in them (eg. Venue)
    # "method / TelegramObject": {"param_to_ignore", ...}
    "send_location": {"latitude", "longitude"},
    "edit_message_live_location": {"latitude", "longitude"},
    "send_venue": {"latitude", "longitude", "title", "address"},
    "send_contact": {"phone_number", "first_name"},
    # The following parameters that are required, but are optional for backward compatibility
    # TODO: Remove this once we drop support for deprecated parameters
    "upload_sticker_file": {"sticker", "sticker_format"},
    "create_new_sticker_set": {"stickers", "sticker_format"},
    "add_sticker_to_set": {"sticker"},
    "InlineQueryResultPhoto": {"thumbnail_url"},
    "InlineQueryResultGif": {"thumbnail_url"},
    "InlineQueryResultMpeg4Gif": {"thumbnail_url"},
    "InlineQueryResultVideo": {"thumbnail_url", "title"},
}


def find_next_sibling_until(tag, name, until):
    for sibling in tag.next_siblings:
        if sibling is until:
            return
        if sibling.name == name:
            return sibling


def parse_table(h4) -> List[List[str]]:
    """Parses the Telegram doc table and has an output of a 2D list."""
    table = find_next_sibling_until(h4, "table", h4.find_next_sibling("h4"))
    if not table:
        return []
    t = []
    for tr in table.find_all("tr")[1:]:
        t.append([td.text for td in tr.find_all("td")])
    return t


def check_method(h4):
    name = h4.text  # name of the method in telegram's docs.
    method = getattr(telegram.Bot, name)  # Retrieve our lib method
    table = parse_table(h4)

    # Check arguments based on source
    sig = inspect.signature(method, follow_wrapped=True)

    checked = []
    for tg_parameter in table:  # Iterates through each row in the table
        # Check if parameter is present in our method
        param = sig.parameters.get(
            tg_parameter[0]  # parameter[0] is first element (the param name)
        )
        assert param is not None, f"Parameter {tg_parameter[0]} not found in {method.__name__}"

        # TODO: Check type via docstring
        # Now check if the parameter is required or not
        assert check_required_param(
            tg_parameter, param, method.__name__
        ), f"Param {param.name!r} of method {method.__name__!r} requirement mismatch!"

        # Now we will check that we don't pass default values if the parameter is not required.
        if param.default is not inspect.Parameter.empty:  # If there is a default argument...
            default_arg_none = check_defaults_type(param)  # check if it's None
            assert default_arg_none, f"Param {param.name!r} of {method.__name__!r} should be None"

        checked.append(tg_parameter[0])

    # The following block of code checks that we don't have extra parameters in our methods
    # that are not in the official docs.

    # Some parameters are ignored for various reasons, so handle them here
    ignored = IGNORED_PARAMETERS.copy()
    backward_compat_args = set()
    if name == "getUpdates":
        ignored -= {"timeout"}  # Has it's own timeout parameter that we do wanna check for
    elif name in (
        f"send{media_type}"
        for media_type in [
            "Animation",
            "Audio",
            "Document",
            "Photo",
            "Video",
            "VideoNote",
            "Voice",
        ]
    ):
        ignored |= {"filename"}  # Convenience parameter
    elif name == "sendContact":
        ignored |= {"contact"}  # Added for ease of use
    elif name in ["sendLocation", "editMessageLiveLocation"]:
        ignored |= {"location"}  # Added for ease of use
    elif name == "sendVenue":
        ignored |= {"venue"}  # Added for ease of use
    elif name == "answerInlineQuery":
        ignored |= {"current_offset"}  # Added for ease of use
    elif name == "sendMediaGroup":
        # Added for ease of use
        ignored |= {"caption", "parse_mode", "caption_entities"}
    elif name in {"createNewStickerSet", "addStickerToSet"}:  # Kept for backward compatibility
        a = {"png_sticker", "emojis", "mask_position", "tgs_sticker", "webm_sticker"}
        ignored |= a
        backward_compat_args |= a
    elif name == "uploadStickerFile":  # Kept for backward compatibility
        ignored |= {"png_sticker"}
        backward_compat_args |= {"png_sticker"}

    assert (sig.parameters.keys() ^ checked) - ignored == set()

    kw_or_positional_args = [
        p.name for p in sig.parameters.values() if p.kind != inspect.Parameter.KEYWORD_ONLY
    ]
    assert (
        set(kw_or_positional_args)
        .difference(checked)
        .difference(["self", "thumb"])
        .difference(backward_compat_args)
        == set()
    ), (
        f"In {method.__qualname__}, extra args should be keyword only "
        f"(compared to {name} in API)"
    )


def check_object(h4):
    name = h4.text
    obj = getattr(telegram, name)
    table = parse_table(h4)

    # Check arguments based on source. Makes sure to only check __init__'s signature & nothing else
    sig = inspect.signature(obj.__init__, follow_wrapped=True)

    checked = set()
    for tg_parameter in table:
        field: str = tg_parameter[0]  # From telegram docs
        if field == "from":
            field = "from_user"
        elif (
            name.startswith("InlineQueryResult")
            or name.startswith("InputMedia")
            or name.startswith("BotCommandScope")
            or name.startswith("MenuButton")
        ) and field == "type":
            continue
        elif (name.startswith("ChatMember")) and field == "status":  # We autofill the status
            continue
        elif (
            name.startswith("PassportElementError") and field == "source"
        ) or field == "remove_keyboard":
            continue
        elif name.startswith("ForceReply") and field == "force_reply":  # this param is always True
            continue

        param = sig.parameters.get(field)
        assert param is not None, f"Attribute {field} not found in {obj.__name__}"
        # TODO: Check type via docstring
        assert check_required_param(
            tg_parameter, param, obj.__name__
        ), f"{obj.__name__!r} parameter {param.name!r} requirement mismatch"

        if param.default is not inspect.Parameter.empty:  # If there is a default argument...
            default_arg_none = check_defaults_type(param)  # check if its None
            assert default_arg_none, f"Param {param.name!r} of {obj.__name__!r} should be `None`"

        checked.add(field)

    ignored = IGNORED_PARAMETERS.copy()
    if name == "InputFile":
        return
    if name == "InlineQueryResult":
        ignored |= {"id", "type"}  # attributes common to all subclasses
    if name == "ChatMember":
        ignored |= {"user", "status"}  # attributes common to all subclasses
    if name == "BotCommandScope":
        ignored |= {"type"}  # attributes common to all subclasses
    if name == "MenuButton":
        ignored |= {"type"}  # attributes common to all subclasses
    elif name in ("PassportFile", "EncryptedPassportElement"):
        ignored |= {"credentials"}
    elif name == "PassportElementError":
        ignored |= {"message", "type", "source"}
    elif name == "InputMedia":
        ignored |= {"caption", "caption_entities", "media", "media_type", "parse_mode"}
    elif name.startswith("InputMedia"):
        ignored |= {"filename"}  # Convenience parameter
    elif name in ("ChatMemberRestricted", "ChatPermissions"):
        ignored |= {"can_send_media_messages"}  # Deprecated param we keep
    elif name in (
        "InlineQueryResultArticle",
        "InlineQueryResultContact",
        "InlineQueryResultDocument",
        "InlineQueryResultLocation",
        "InlineQueryResultVenue",
    ):
        ignored |= {"thumb_height", "thumb_width"}  # Deprecated params we keep
    elif name in ("InlineQueryResultGif", "InlineQueryResultMpeg4Gif"):
        ignored |= {"thumb_mime_type"}  # Deprecated param we keep

    assert (sig.parameters.keys() ^ checked) - ignored == set()


def is_parameter_required_by_tg(field: str) -> bool:
    if field in {"Required", "Yes"}:
        return True
    if field.split(".", 1)[0] == "Optional":  # splits the sentence and extracts first word
        return False
    else:
        return True


def check_required_param(
    param_desc: List[str], param: inspect.Parameter, method_or_obj_name: str
) -> bool:
    """Checks if the method/class parameter is a required/optional param as per Telegram docs.

    Returns:
        :obj:`bool`: The boolean returned represents whether our parameter's requirement (optional
        or required) is the same as Telegram's or not.
    """
    is_ours_required = param.default is inspect.Parameter.empty
    telegram_requires = is_parameter_required_by_tg(param_desc[2])
    # Handle cases where we provide convenience intentionally-
    if param.name in ignored_param_requirements.get(method_or_obj_name, {}):
        return True
    return telegram_requires is is_ours_required


def check_defaults_type(ptb_param: inspect.Parameter) -> bool:
    return True if DefaultValue.get_value(ptb_param.default) is None else False


to_run = env_var_2_bool(os.getenv("TEST_OFFICIAL"))
argvalues = []
names = []

if to_run:
    argvalues = []
    names = []
    request = httpx.get("https://core.telegram.org/bots/api")
    soup = BeautifulSoup(request.text, "html.parser")

    for thing in soup.select("h4 > a.anchor"):
        # Methods and types don't have spaces in them, luckily all other sections of the docs do
        # TODO: don't depend on that
        if "-" not in thing["name"]:
            h4 = thing.parent

            # Is it a method
            if h4.text[0].lower() == h4.text[0]:
                argvalues.append((check_method, h4))
                names.append(h4.text)
            elif h4.text not in IGNORED_OBJECTS:  # Or a type/object
                argvalues.append((check_object, h4))
                names.append(h4.text)


@pytest.mark.skipif(not to_run, reason="test_official is not enabled")
@pytest.mark.parametrize(("method", "data"), argvalues=argvalues, ids=names)
def test_official(method, data):
    method(data)
