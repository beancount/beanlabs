"""Convenient all-purpose Google APIs credentialer."""

__copyright__ = "Copyright (C) 2013-2020  Martin Blais"
__license__ = "GNU GPLv2"

import json
import logging
import pickle
from os import path
from typing import List, Optional


from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport import requests as grequests


def get_credentials(scopes: List[str],
                    secrets_filename: Optional[str] = None,
                    storage_filename: Optional[str] = None):
    """Authenticate via oauth2 and return credentials."""
    logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

    if None in {secrets_filename, storage_filename}:
        import __main__  # pylint: disable=import-outside-toplevel
        cache_basename = path.expanduser(
            path.join("~/.google", path.splitext(path.basename(__main__.__file__))[0]))
    if secrets_filename is None:
        secrets_filename = "{}.json".format(cache_basename)
    if storage_filename is None:
        storage_filename = "{}.cache".format(cache_basename)

    # Load the secrets file, to figure if it's for a service account or an OAUTH
    # secrets file.
    secrets_info = json.load(open(secrets_filename))
    if secrets_info.get("type") == "service_account":
        # Process service account flow.
        # pylint: disable=import-outside-toplevel
        import google.oauth2.service_account as sa
        credentials = sa.Credentials.from_service_account_info(
            secrets_info, scopes=scopes)
    else:
        # Process OAuth flow.
        credentials = None
        if path.exists(storage_filename):
            with open(storage_filename, 'rb') as token:
                credentials = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(grequests.Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    secrets_filename, scopes)
                credentials = flow.run_console()
            # Save the credentials for the next run
            with open(storage_filename, 'wb') as token:
                pickle.dump(credentials, token)

    return credentials
