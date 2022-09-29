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
"""This module contains the ChatJoinRequestHandler class."""

from typing import Optional

from telegram import Update
from telegram._utils.defaultvalue import DEFAULT_TRUE
from telegram._utils.types import RT, SCT, DVInput
from telegram.ext._handler import BaseHandler
from telegram.ext._utils.types import CCT, HandlerCallback


class ChatJoinRequestHandler(BaseHandler[Update, CCT]):
    """BaseHandler class to handle Telegram updates that contain
    :attr:`telegram.Update.chat_join_request`.

    Note:
        If either the :paramref:`username` or the :paramref:`chat_id` corresponds to one
        in the appropriate, the request will be passed to this handler.

        .. versionadded:: 20.0

    Warning:
        When setting :paramref:`block` to :obj:`False`, you cannot rely on adding custom
        attributes to :class:`telegram.ext.CallbackContext`. See its docs for more info.

    .. versionadded:: 13.8

    Args:
        callback (:term:`coroutine function`): The callback function for this handler. Will be
            called when :meth:`check_update` has determined that an update should be processed by
            this handler. Callback signature::

                async def callback(update: Update, context: CallbackContext)

            The return value of the callback is usually ignored except for the special case of
            :class:`telegram.ext.ConversationHandler`.
        chat_id (:obj:`int` | Collection[:obj:`int`], optional): Filters requests to allow only
            those which are asking to join the specified chat ID(s).

            .. versionadded:: 20.0
        username (:obj:`str` | Collection[:obj:`str`], optional): Filters requests to allow only
            those which are asking to join the specified username(s).
            Leading ``'@'`` in username will be discarded.

            .. versionadded:: 20.0
        block (:obj:`bool`, optional): Determines whether the return value of the callback should
            be awaited before processing the next handler in
            :meth:`telegram.ext.Application.process_update`. Defaults to :obj:`True`.

    Attributes:
        callback (:term:`coroutine function`): The callback function for this handler.
        block (:obj:`bool`): Determines whether the callback will run in a blocking way..

    """

    __slots__ = (
        "_chat_ids",
        "_usernames",
    )

    def __init__(
        self,
        callback: HandlerCallback[Update, CCT, RT],
        chat_id: SCT[int] = None,
        username: SCT[str] = None,
        block: DVInput[bool] = DEFAULT_TRUE,
    ):
        super().__init__(callback, block=block)

        self._chat_ids = self._parse_chat_id(chat_id)
        self._usernames = self._parse_username(username)

    @staticmethod
    def _parse_chat_id(chat_id: Optional[SCT[int]]) -> frozenset[int]:
        if chat_id is None:
            return frozenset()
        if isinstance(chat_id, int):
            return frozenset({chat_id})
        return frozenset(chat_id)

    @staticmethod
    def _parse_username(username: Optional[SCT[str]]) -> frozenset[str]:
        if username is None:
            return frozenset()
        if isinstance(username, str):
            return frozenset({username[1:] if username.startswith("@") else username})
        return frozenset({usr[1:] if usr.startswith("@") else usr for usr in username})

    def check_update(self, update: object) -> bool:
        """Determines whether an update should be passed to this handler's :attr:`callback`.

        Args:
            update (:class:`telegram.Update` | :obj:`object`): Incoming update.

        Returns:
            :obj:`bool`

        """
        if isinstance(update, Update) and update.chat_join_request:
            if not self._chat_ids and not self._usernames:
                return True
            if update.chat_join_request.chat.id in self._chat_ids:
                return True
            if update.chat_join_request.from_user.username in self._usernames:
                return True
            return False
        return False
