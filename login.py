"""
Copied from
https://github.com/adw0rd/instagrapi/blob/abea0b7cf584f08852a1d3b23c97555c9731a428/docs/usage-guide/best-practices.md?plain=1#L89-L138
"""

import logging
from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import LoginRequired

logger = logging.getLogger()


def login_user(cl: Client, username: str) -> None:
    """
    Attempts to login to Instagram using either the provided session information
    or the provided username and password.
    """
    password = ""
    totp = ""

    SETTINGS = Path("session.json")

    try:
        session = cl.load_settings(SETTINGS)
    except FileNotFoundError:
        session = None

    login_via_session = False
    login_via_pw = False

    if session:
        try:
            cl.set_settings(session)
            cl.login(username, password)

            # check if session is valid
            try:
                cl.get_timeline_feed()
            except LoginRequired:
                logger.info(
                    "Session is invalid, need to login via username and password"
                )

                old_session = cl.get_settings()

                # use the same device uuids across logins
                cl.set_settings({})
                cl.set_uuids(old_session["uuids"])

                cl.login(username, password)
            login_via_session = True
        except Exception as e:
            logger.info("Couldn't login user using session information: %s", e)

    if not login_via_session:
        password = input(f"Enter a password for instagram account {username}: ")
        totp = input(f"Auth code, if applicable: ")
        try:
            logger.info(
                "Attempting to login via username and password. username: %s", username
            )
            if cl.login(username, password, verification_code=totp):
                login_via_pw = True
        except Exception as e:
            logger.info("Couldn't login user using username and password: %s", e)

    if not login_via_pw and not login_via_session:
        raise Exception("Couldn't login user with either password or session")

    cl.dump_settings(SETTINGS)
