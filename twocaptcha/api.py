#!/usr/bin/env python3

import requests
import contextlib


class NetworkException(Exception):
    pass


class ApiException(Exception):
    pass


class ApiClient():
    def __init__(self, post_url = '2captcha.com'):
        self.post_url = post_url
        
        
    def in_(self, files={}, **kwargs):
        '''
        
        sends POST-request (files and/or params) to solve captcha

        Parameters
        ----------
        files : dict, optional
            A dictionary of file parameters to send. Keys are form field names,
            values are file paths (e.g., {'file': 'path/to/captcha.jpg'}).
            The default is {}.
        **kwargs : dict
            Arbitrary keyword arguments for other POST parameters (e.g., key='YOUR_API_KEY', method='post').

        Raises
        ------
        NetworkException
            If a network error occurs (e.g., connection refused, bad status code).
        ApiException
            If the API returns an error (e.g., 'ERROR_WRONG_USER_KEY').

        Returns
        -------
        resp : str
            The API response text. Typically an ID for the captcha if successful, or an error message.

        '''

        try:
            current_url = f'https://{self.post_url}/in.php'
            if files:
                with contextlib.ExitStack() as stack:
                    opened_files = {
                        key: stack.enter_context(open(path, 'rb'))
                        for key, path in files.items()
                    }
                    resp = requests.post(current_url,
                                         data=kwargs,
                                         files=opened_files)
                # Files are now automatically closed when exiting the 'with' block
            elif 'file' in kwargs:
                with open(kwargs.pop('file'), 'rb') as f:
                    resp = requests.post(current_url,
                                         data=kwargs,
                                         files={'file': f})
            else:
                resp = requests.post(current_url,
                                     data=kwargs)

        except requests.RequestException as e:
            raise NetworkException(e)

        if resp.status_code != 200:
            raise NetworkException(f'bad response: {resp.status_code}')

        resp = resp.text

        if 'ERROR' in resp:
            raise ApiException(resp)

        return resp

    def res(self, **kwargs):
        '''
        sends additional GET-requests (solved captcha, balance, report etc.)

        Parameters
        ----------
        **kwargs : dict
            Arbitrary keyword arguments for GET parameters (e.g., key='YOUR_API_KEY', action='get', id='CAPTCHA_ID').

        Raises
        ------
        NetworkException
            If a network error occurs (e.g., connection refused, bad status code).
        ApiException
            If the API returns an error (e.g., 'ERROR_WRONG_USER_KEY').

        Returns
        -------
        resp : str
            The API response text. For 'get' action, this could be the solved captcha text or a 'CAPCHA_NOT_READY' message.

        '''

        try:
            current_url_out = f'https://{self.post_url}/res.php'
            resp = requests.get(current_url_out, params=kwargs)

            if resp.status_code != 200:
                raise NetworkException(f'bad response: {resp.status_code}')

            resp = resp.text

            if 'ERROR' in resp:
                raise ApiException(resp)

        except requests.RequestException as e:
            raise NetworkException(e)

        return resp
