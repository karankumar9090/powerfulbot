#!/usr/bin/env python
#
# A library that provides a Python interface to the Telegram Bot API
# Copyright (C) 2015-2018
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
"""This module contains the Promise class."""

import logging
from threading import Event


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Promise(object):
    """A simple Promise implementation for use with the run_async decorator, DelayQueue etc.

    Args:
        pooled_function (callable): The callable that will be called concurrently.
        args (list|tuple): Positional arguments for ``pooled_function``
        kwargs (dict): Keyword arguments for ``pooled_function``

    Attributes:
        pooled_function (callable): The callable that will be called concurrently.
        args (list|tuple): Positional arguments for ``pooled_function``
        kwargs (dict): Keyword arguments for ``pooled_function``
        done (:obj:`Event`): Is set when the result is available.

    """

    def __init__(self, pooled_function, args, kwargs):
        self.pooled_function = pooled_function
        self.args = args
        self.kwargs = kwargs
        self.done = Event()
        self._result = None
        self._exception = None

    def run(self):
        """Calls the ``pooled_function`` callable."""

        try:
            self._result = self.pooled_function(*self.args, **self.kwargs)

        except Exception as exc:
            logger.exception('An uncaught error was raised while running the promise')
            self._exception = exc

        finally:
            self.done.set()

    def __call__(self):
        """Calls run()"""
        self.run()

    def result(self, timeout=None):
        """Return the result of the ``Promise``.

        Args:
            timeout (:obj:`float`, optional): Maximum time in seconds to wait for the result to be
                calculated. ``None`` means indefinite. Default is ``None``.

        Returns:
            Returns the return value of ``pooled_function`` or ``None`` if the ``timeout`` expires.

        Raises:
            Any exception raised by ``pooled_function``.
        """
        self.done.wait(timeout=timeout)
        if self._exception is not None:
            raise self._exception  # pylint: disable=raising-bad-type
        return self._result

    @property
    def exception(self):
        """The exception raised by ``pooled_function`` or ``None`` if no exception has been raised
        (yet)."""
        return self._exception
