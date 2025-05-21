#!/usr/bin/env python3

import os
import os
import sys
import time
import requests
import base64 # For b64encode and b64decode
import re # For base64 regex check
from urllib.parse import urlparse # For URL validation


# Future Enhancement: Consider adding type hints throughout this module
# for improved code clarity, maintainability, and to help developers
# understand the expected types for parameters, especially for the
# various captcha solving methods and their diverse options.


try:
    from .api import ApiClient

except ImportError:
    from api import ApiClient


class SolverExceptions(Exception):
    pass


class ValidationException(SolverExceptions):
    pass


class NetworkException(SolverExceptions):
    pass


class ApiException(SolverExceptions):
    pass


class TimeoutException(SolverExceptions):
    pass


class TwoCaptcha():
    def __init__(self,
                 api_key,
                 soft_id=4580,
                 callback=None,
                 default_timeout=120,
                 recaptcha_timeout=600,
                 polling_interval=10,
                 server = '2captcha.com'):

        self.api_key = api_key
        self.soft_id = soft_id
        self.callback = callback
        self.default_timeout = default_timeout
        self.recaptcha_timeout = recaptcha_timeout
        self.polling_interval = polling_interval
        self.api_client = ApiClient(post_url = str(server))
        self.max_files = 9
        self.exceptions = SolverExceptions

    def _is_base64_like(self, s, strict_check=False):
        """
        Checks if a string is base64 like.
        If strict_check is True, it validates padding and character set.
        Otherwise, it does a more lenient check.
        """
        if not isinstance(s, str) or not s:
            return False

        # Basic check for typical base64 characters and length
        # A more lenient check might only ensure it's ASCII and has appropriate length.
        if len(s) < 20: # Too short for typical image base64
            return False
        
        # Check if the string consists of valid base64 characters.
        # This regex allows for optional padding.
        if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', s): # Use re from top-level import
            return False

        if len(s) % 4 != 0 and strict_check: # Must be multiple of 4 if strictly checking padding
             return False

        try:
            # The validate=True option is not available in base64.b64decode
            # We decode and then re-encode to see if it matches. This is a common way.
            # However, for a "like" check, just attempting to decode is often enough.
            decoded_data = base64.b64decode(s)
            if strict_check:
                # Re-encode and check if it matches the original string (this handles padding issues)
                if base64.b64encode(decoded_data).decode('utf-8') != s.rstrip('='): # Compare without padding on original if needed
                     # This check can be too strict if original base64 had variable padding
                     pass # For now, successful decode is enough for "like"
            return True
        except (TypeError, base64.binascii.Error):
            return False
        return False


    def normal(self, file_input, **kwargs):
        '''Wrapper for solving normal captcha (image).

        Parameters
        __________
        file_input : str or file-like object
            Captcha image as a file path (str), URL (str), or base64 encoded string (str).
        body : str
            (Deprecated in favor of file_input auto-detection) Base64-encoded captcha image.
        phrase : int, optional
            0 - captcha contains one word. 1 - captcha contains two or more words.
            Default: 0.
        numeric : int, optional
            0 - not specified. 1 - captcha contains only numbers. 2 - captcha contains only letters. 3 - captcha
            contains only numbers OR only letters. 4 - captcha MUST contain both numbers AND letters.
            Default: 0
        min_len : int, optional
            0 - not specified. 1..20 - minimal number of symbols in captcha.
            Default: 0.
        max_len : int, optional
            0 - not specified. 1..20 - maximal number of symbols in captcha.
            Default: 0.
        case_sensitive : int, optional
            0 - captcha in not case sensitive. 1 - captcha is case sensitive.
            Default: 0.
        calc : int, optional
            0 - not specified. 1 - captcha requires calculation (e.g. type the result 4 + 8 = ).
            Default: 0.
        lang : str, optional
            Language code. See the list of supported languages https://2captcha.com/2captcha-api#language.
        hint_text : str, optional
            Max 140 characters. Endcoding: UTF-8. Text will be shown to worker to help him to solve the captcha correctly.
            For example: type red symbols only.
        hint_img : img, optional
            Max 400x150px, 100 kB. Image with instruction for solving reCAPTCHA. Not required if you're sending
            instruction as text with textinstructions.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        '''

        # file_input is the primary way to specify the image
        # The 'body' kwarg is supported for backward compatibility if someone passes it directly.
        if 'body' in kwargs and kwargs.get('body') and not file_input:
             # If body is provided and file_input is not, treat body as the primary input
             method_params = {'method': 'base64', 'body': kwargs.pop('body')}
        elif file_input:
             method_params = self.get_method(file_input)
        else:
            raise ValidationException(
                "Captcha image not provided. Use 'file_input' parameter or 'body' keyword argument."
            )
        
        result = self.solve(**method_params, **kwargs)
        return result

    def audio(self, file_input, lang, **kwargs):
        '''Wrapper for solving audio captcha.

        Parameters
        __________
        file_input : str
            Audio captcha as a URL to an mp3, a local mp3 file path, or a base64 encoded mp3 string.
        lang : str
          The language of audio record. Supported languages are: "en", "ru", "de", "el", "pt", "fr".
        '''
        if not file_input:
            raise ValidationException('Audio input (file_input) is required.')

        if not lang or lang not in ("en", "ru", "de", "el", "pt", "fr"):
            raise ValidationException(f'Unsupported lang: {lang}. Supported: "en", "ru", "de", "el", "pt", "fr".')

        body_content = None
        # Try to determine the type of file_input
        if isinstance(file_input, str):
            if file_input.startswith('http'):
                try:
                    response = requests.get(file_input, timeout=10) # Added timeout
                    response.raise_for_status() # Raises an exception for bad status codes
                    # Assuming it's mp3 if downloaded from URL, API will validate format
                    body_content = base64.b64encode(response.content).decode('utf-8')
                except requests.RequestException as e:
                    raise ValidationException(f'Failed to download audio from URL: {file_input}. Error: {e}')
            elif os.path.exists(file_input):
                if not file_input.lower().endswith(".mp3"):
                    raise ValidationException('File extension must be .mp3 for local audio files.')
                with open(file_input, "rb") as media:
                    body_content = base64.b64encode(media.read()).decode('utf-8')
            elif self._is_base64_like(file_input): # Check if it's a base64 string
                # Assuming it's an mp3 if it's base64, API will validate format
                body_content = file_input
            else:
                raise ValidationException('Invalid audio file_input. Must be a URL, an existing .mp3 file path, or a base64 string.')
        else:
            raise ValidationException('Audio file_input must be a string (URL, path, or base64).')
        
        if not body_content:
             raise ValidationException('Could not process audio input.')

        result = self.solve(body=body_content, method='audio', lang=lang, **kwargs) # API expects 'audio' as method for this
        return result

    def text(self, text, **kwargs):
        '''Wrapper for solving text captcha.

        Parameters
        __________
        text : str
            Max 140 characters. Endcoding: UTF-8. Text will be shown to worker to help him to solve the captcha correctly.
            For example: type red symbols only.
        lang: str, optional
            Language code. See the list of supported languages https://2captcha.com/2captcha-api#language.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        '''

        result = self.solve(text=text, method='post', **kwargs)
        return result

    def recaptcha(self, site_key, url, version='v2', enterprise=0, **kwargs):
        '''Wrapper for solving recaptcha (v2, v3).

        Parameters
        _______________
        site_key : str
            Value of sitekey parameter you found on page.
        url : str
            Full URL of the page where you see the reCAPTCHA.
        domain : str, optional
            Domain used to load the captcha: google.com or recaptcha.net. Default: google.com.
        invisible : int, optional
            1 - means that reCAPTCHA is invisible. 0 - normal reCAPTCHA. Default: 0.
        version : str, optional
            v3 — defines that you're sending a reCAPTCHA V3. Default: v2.
        enterprise : str, optional
            1 - defines that you're sending reCAPTCHA Enterpise. Default: 0.
        action : str, optional
            Value of action parameter you found on page. Default: verify.
        score : str, only for v3, optional
            The score needed for resolution. Currently, it's almost impossible to get token with score higher than 0.3.
            Default: 0.4.
        data-s : str, only for v2, optional
            Value of data-s parameter you found on page. Curenttly applicable for Google Search and other Google services.
        cookies : str, only for v2, optional
            Your cookies that will be passed to our worker who solve the captha. We also return worker's cookies in the
            response if you use json=1. Format: KEY:Value, separator: semicolon, example: KEY1:Value1;KEY2:Value2;
        userAgent : str, only for v2, optional
            Your userAgent that will be passed to our worker and used to solve the captcha.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        params = {
            'googlekey': site_key,
            'url': url,
            'method': 'userrecaptcha',
            'version': version,
            'enterprise': enterprise,
            **kwargs,
        }

        result = self.solve(timeout=self.recaptcha_timeout, **params)
        return result

    def funcaptcha(self, site_key, url, **kwargs):
        '''Wrapper for solving funcaptcha.

        Parameters
        __________
        site_key : str
            Value of pk or data-pkey parameter you found on page.
        url : str
            Full URL of the page where you see the FunCaptcha.
        surl : str, optional
            Value of surl parameter you found on page.
        user_agent: str, optional
            Tells us to use your user-agent value.
        data[key] : str, optional
            Custom data to pass to FunCaptcha. For example: data[blob]=stringValue.
        soft_id : str, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(publickey=site_key,
                            url=url,
                            method='funcaptcha',
                            **kwargs)
        return result

    def geetest(self, gt, challenge, url, **kwargs):
        '''Wrapper for solving geetest captcha.

        Parameters:
        __________
        gt : str
            Value of gt parameter you found on target website.
        challenge : str
            Value of challenge parameter you found on target website.
        url : str
            Full URL of the page where you see Geetest captcha.
        offline : num, optional
            In rare cases initGeetest can be called with offline parameter. If the call uses offline: true, set the
            value to 1. Default: 0.
        new_captcha : num, optional
            In rare cases initGeetest can be called with new_captcha parameter. If the call uses new_captcha: true, set
            the value to 1. Mostly used with offline parameter.
        user_agent : str, optional
            Your userAgent that will be passed to our worker and used to solve the captcha.
        api_server : str, optional
            Value of api_server parameter you found on target website.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(gt=gt,
                            challenge=challenge,
                            url=url,
                            method='geetest',
                            **kwargs)
        return result

    def hcaptcha(self, site_key, url, **kwargs):
        '''Wrapper for solving hcaptcha.

        Parameters
        __________
        site_key : str
            Value of data-sitekey parameter you found on page.
        url : str
            Full URL of the page where you bypass the captcha.
        invisible : num, optional
            Use 1 for invisible version of hcaptcha. Currently it is a very rare case.
            Default: 0.
        data : str, optional
            Custom data that is used in some implementations of hCaptcha, mostly with invisible=1. In most cases you see
            it as rqdata inside network requests. Format: "data": "rqDataValue".
        domain : str, optional
            Domain used to load the captcha: hcaptcha.com or js.hcaptcha.com. Default: hcaptcha.com.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(sitekey=site_key,
                            url=url,
                            method='hcaptcha',
                            **kwargs)
        return result

    def keycaptcha(self, s_s_c_user_id, s_s_c_session_id,
                   s_s_c_web_server_sign, s_s_c_web_server_sign2, url,
                   **kwargs):
        '''Wrapper for solving.

        Parameters
        __________
        s_s_c_user_id : str
            Value of s_s_c_user_id parameter you found on page.
        s_s_c_session_id : str
            Value of s_s_c_session_id parameter you found on page.
        s_s_c_web_server_sign : str
            Value of s_s_c_web_server_sign parameter you found on page.
        s_s_c_web_server_sign2 : str
            Value of s_s_c_web_server_sign2 parameter you found on page.
        url : str
            Full URL of the page where you see the KeyCaptcha.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        params = {
            's_s_c_user_id': s_s_c_user_id,
            's_s_c_session_id': s_s_c_session_id,
            's_s_c_web_server_sign': s_s_c_web_server_sign,
            's_s_c_web_server_sign2': s_s_c_web_server_sign2,
            'url': url,
            'method': 'keycaptcha',
            **kwargs,
        }

        result = self.solve(**params)
        return result

    def capy(self, site_key, url, **kwargs):
        '''Wrapper for solving capy.

        Parameters
        __________
        site_key : str
            The domain part of script URL you found on page. Default value: https://jp.api.capy.me/.
        url : str
            Full URL of the page where you see the captcha.
        api_server : str, optional
            The domain part of script URL you found on page. Default value: https://jp.api.capy.me/.
        version : str, optional
            The version of captcha task: puzzle (assemble a puzzle) or avatar (drag an object). Default: puzzle.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(captchakey=site_key,
                            url=url,
                            method='capy',
                            **kwargs)
        return result

    def grid(self, file_input, **kwargs):
        '''Wrapper for solving grid captcha (image).

        Required:
        file_input : str or file-like object
            Captcha image as a file path, URL, or base64 encoded string.
        body : str
            (Deprecated) Base64-encoded captcha image.
        hintText : str
            Max 140 characters. Endcoding: UTF-8. Text with instruction for solving reCAPTCHA. For example: select images
            with trees. Not required if you're sending instruction as an image with imginstructions.
        hint_img : img
            Max 400x150px, 100 kB. Image with instruction for solving reCAPTCHA. Not required if you're sending
            instruction as text with textinstructions.
        rows : int, optional
            Number of rows in reCAPTCHA grid.
        cols : itn, optional
            Number of columns in reCAPTCHA grid.
        previous_id : str, optional
            Id of your previous request with the same captcha challenge.
        can_skip : int, optional
            0 - not specified. 1 - possibly there's no images that fit the instruction. Set the value to 1 only if it's
            possible that there's no images matching to the instruction. We'll provide a button "No matching images" to
            worker, and you will receive No_matching_images as answer.
            Default: 0.
        lang: str, optional
            Language code. See the list of supported languages https://2captcha.com/2captcha-api#language.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''
        if 'body' in kwargs and kwargs.get('body') and not file_input:
             method_params = {'method': 'base64', 'body': kwargs.pop('body')}
        elif file_input:
             method_params = self.get_method(file_input)
        else:
            raise ValidationException(
                "Captcha image not provided. Use 'file_input' or 'body'."
            )

        params = {
            'recaptcha': 1,
            **method_params,
            **kwargs,
        }

        result = self.solve(**params)
        return result

    def canvas(self, file_input, **kwargs):
        '''Wrapper for solving canvas captcha (image).

        Parameters
        __________
        file_input : str or file-like object
            Captcha image as a file path, URL, or base64 encoded string.
        body : str
            (Deprecated) Base64-encoded captcha image.
        hintText : str
            Max 140 characters. Endcoding: UTF-8. Text with instruction for solving reCAPTCHA. For example: select
            images with trees. Not required if you're sending instruction as an image with imginstructions.
        hint_img : img
            Max 400x150px, 100 kB. Image with instruction for solving reCAPTCHA. Not required if you're sending
            instruction as text with textinstructions.
        can_skip : int, optional
            0 - not specified. 1 - possibly there's no images that fit the instruction. Set the value to 1 only if it's
            possible that there's no images matching to the instruction. We'll provide a button "No matching images" to
            worker, and you will receive No_matching_images as answer.
            Default: 0.
        lang : int, optional
            0 - not specified. 1 - Cyrillic captcha. 2 - Latin captcha.
            Default: 0.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        '''

        if not ('hint_text' in kwargs or 'hint_img' in kwargs):
            raise ValidationException(
                'parameters required: hint_text and/or hint_img')
        
        if 'body' in kwargs and kwargs.get('body') and not file_input:
             method_params = {'method': 'base64', 'body': kwargs.pop('body')}
        elif file_input:
             method_params = self.get_method(file_input)
        else:
            raise ValidationException(
                "Captcha image not provided. Use 'file_input' or 'body'."
            )

        params = {
            'recaptcha': 1,
            'canvas': 1,
            **method_params,
            **kwargs,
        }

        result = self.solve(**params)
        return result

    def coordinates(self, file_input, **kwargs):
        '''Wrapper for solving coordinates captcha (image).

        Parameters
        __________
        file_input : str or file-like object
            Captcha image as a file path, URL, or base64 encoded string.
        body : str
            (Deprecated) Base64-encoded captcha image.
        hintText : str
            Max 140 characters. Endcoding: UTF-8. Text with instruction for solving the captcha. For example: click on
            images with ghosts. Not required if the image already contains the instruction.
        hint_img : img
             Max 400x150px, 100 kB. Image with instruction for solving reCAPTCHA. Not required if you're sending
             instruction as text with textinstructions.
        lang : str, optional
            Language code. See the list of supported languages https://2captcha.com/2captcha-api#language.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        '''
        if 'body' in kwargs and kwargs.get('body') and not file_input:
             method_params = {'method': 'base64', 'body': kwargs.pop('body')}
        elif file_input:
             method_params = self.get_method(file_input)
        else:
            raise ValidationException(
                "Captcha image not provided. Use 'file_input' or 'body'."
            )

        params = {
            'coordinatescaptcha': 1,
            **method_params,
            **kwargs,
        }

        result = self.solve(**params)
        return result

    def rotate(self, files_input, **kwargs):
        '''Wrapper for solving rotate captcha (image).

        Parameters
        __________
        files_input : str, list of str, or dict of str
            Can be a single image (URL, path, base64 string), 
            a list of image paths, or a dictionary of image paths.
        body : str 
            (Deprecated) Base64-encoded captcha image for single string input.
        angle : int, optional
            Angle for one rotation step in degrees. If not defined we'll use the default value for FunCaptcha: 40 degrees.
            Default: 40.
        lang : str, optional
            Language code. See the list of supported languages https://2captcha.com/2captcha-api#language.
        hint_img : str, optional
            Image with instruction for worker to help him to solve captcha correctly.
        hint_text : str, optional
            Text will be shown to worker to help him to to solve captcha correctly.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        if isinstance(files_input, str):
            # Handle single image input (URL, path, or base64)
            # Prefer file_input if 'body' is also in kwargs but file_input is given
            if 'body' in kwargs and kwargs.get('body') and not files_input:
                 input_details = {'method': 'base64', 'body': kwargs.pop('body')}
            elif files_input:
                 input_details = self.get_method(files_input) # Use refactored get_method
            else:
                raise ValidationException("Captcha image not provided for rotate method.")

            # Prepare params for self.solve() based on what get_method returned
            solve_params = {'method': 'rotatecaptcha'}
            if input_details['method'] == 'base64':
                solve_params['body'] = input_details['body']
            else: # 'post'
                solve_params['file'] = input_details['file']
            
            solve_params.update(kwargs)
            result = self.solve(**solve_params)
            return result

        elif isinstance(files_input, dict):
            processed_files_input = list(files_input.values())
        elif isinstance(files_input, list):
            processed_files_input = files_input
        else:
            raise ValidationException("Invalid 'files_input' type. Expected str, list, or dict.")

        # Assumes extract_files expects a list of file paths
        # and is used for multi-image rotate captchas.
        extracted_files_dict = self.extract_files(processed_files_input)

        result = self.solve(files=extracted_files_dict, method='rotatecaptcha', **kwargs)
        return result
    

    def geetest_v4(self, captcha_id, url, **kwargs):
        '''Wrapper for solving geetest_v4 captcha.

        Parameters
        __________
        captcha_id : str
            Value of captcha_id parameter you found on target website.
        url: str
            Full URL of the page where you see Geetest captcha.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(captcha_id=captcha_id,
                            url=url,
                            method='geetest_v4',
                            **kwargs)
        return result
    

    def lemin(self, captcha_id, div_id, url, **kwargs):
        '''Wrapper for solving Lemin Cropped Captcha.

        Parameters
        __________
        captcha_id : str
            Value of captcha_id parameter you found on page.
        div_id : str
            The id of captcha parent div element.
        url : str
            Full URL of the page where you see the captcha.
        api_server : str, optional
            The domain part of script URL you found on page. Default value: https://api.leminnow.com/.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(captcha_id=captcha_id,
                            div_id=div_id,
                            url=url,
                            method='lemin',
                            **kwargs)
        return result

    def atb_captcha(self, app_id, api_server_url, url, **kwargs):
        '''Wrapper for solving atbCAPTCHA.

        Parameters
        __________
        app_id : str
            The value of appId parameter in the website source code.
        api_server_url : str
            The value of apiServer parameter in the website source code.
        url : str
            The full URL of target web page where the captcha is loaded. We do not open the page, not a problem if it is
            available only for authenticated users.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.

        '''

        result = self.solve(app_id=app_id,
                            api_server=api_server_url, # maps to 'api_server' in rename_params
                            url=url,
                            method='atb_captcha',
                            **kwargs)
        return result
    

    def turnstile(self, site_key, url, **kwargs):
        '''Wrapper for solving Cloudflare Turnstile.

        Parameters
        __________
        site_key : str
            Value of sitekey parameter you found on page.
        url : str
            Full URL of the page where you see the captcha.
        action : str. optional
            Value of optional action parameter you found on page, can be defined in data-action attribute or passed
            to turnstile.render call.
        data : str, optional
            The value of cData passed to turnstile.render call. Also can be defined in data-cdata attribute.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(sitekey=site_key,
                            url=url,
                            method='turnstile',
                            **kwargs)
        return result
    

    def amazon_waf(self, site_key, iv, context, url, **kwargs):
        '''Wrapper for solving Amazon WAF.

        Parameters
        __________
        site_key : str
            Value of key parameter you found on the page.
        iv : str
            Value of iv parameter you found on the page.
        context : str
            Value of optional context parameter you found on page.
        url : str
            Full URL of the page where you see the captcha.
        challenge_script : str, optional
            The source URL of challenge.js script on the page.
        captcha_script : str, optional
            The source URL of captcha.js script on the page.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(sitekey=site_key,
                            iv=iv, 
                            context=context,
                            url=url,
                            method='amazon_waf',
                            **kwargs)
        
        return result

    def mtcaptcha(self, site_key, url, **kwargs):
        '''Wrapper for solving MTCaptcha.

        Parameters
        __________
        site_key : str
            The value of sitekey parameter found on the page.
        url : str
            Full URL of the page where you solve the captcha.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(sitekey=site_key,
                            url=url,
                            method='mt_captcha',
                            **kwargs)
        return result

    def friendly_captcha(self, site_key, url, **kwargs):
        '''Wrapper for solving Friendly Captcha.

        Parameters
        __________
        site_key : str
            The value of data-sitekey attribute of captcha's div element on page.
        url : str
            Full URL of the page where you solve the captcha.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(sitekey=site_key,
                            url=url,
                            method='friendly_captcha',
                            **kwargs)
        return result

    def tencent(self, app_id, url, **kwargs):
        '''Wrapper for solving Tencent captcha.

        Parameters
        __________
        app_id : str
            The value of appId parameter in the website source code.
        url : str
            The full URL of target web page where the captcha is loaded. We do not open the page, not a problem if it is
            available only for authenticated users.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(app_id=app_id,
                            url=url,
                            method="tencent",
                            **kwargs)
        return result

    def cutcaptcha(self, misery_key, apikey, url, **kwargs):
        '''Wrapper for solving Friendly Captcha.

        Parameters
        __________
        misery_key : str
            The value of CUTCAPTCHA_MISERY_KEY variable defined on page.
        api_key_param : str # Renamed from apikey to avoid conflict with self.api_key
            The value of data-apikey attribute of iframe's body. Also, the name of javascript file included on the page.
        url : str
            Full URL of the page where you solve the captcha.
        soft_id : int, optional
            ID of software developer. Developers who integrated their software with 2Captcha get reward: 10% of
            spendings of their software users.
        callback : str, optional
            URL for pingback (callback) response that will be sent when captcha is solved. URL should be registered on
            the server. More info here https://2captcha.com/2captcha-api#pingback.
        proxy : dict, optional
            {'type': 'HTTPS', 'uri': 'login:password@IP_address:PORT'}.
        '''

        result = self.solve(misery_key=misery_key,
                            api_key=api_key_param, # maps to 'api_key' in rename_params
                            url=url,
                            method='cutcaptcha',
                            **kwargs)
        return result

    def solve(self, timeout=0, polling_interval=0, **kwargs):
        '''Sends captcha, receives result.

        Parameters
        __________
        timeout : float

        polling_interval : int

        **kwargs : dict
            all captcha params

        Returns

        result : string
        '''

        id_ = self.send(**kwargs)
        result = {'captchaId': id_}

        if self.callback is None:

            timeout = float(timeout or self.default_timeout)
            sleep = int(polling_interval or self.polling_interval)

            code = self.wait_result(id_, timeout, sleep)
            result.update({'code': code})

        return result

    def wait_result(self, id_, timeout, polling_interval):

        max_wait = time.time() + timeout

        while time.time() < max_wait:

            try:
                return self.get_result(id_)

            except NetworkException:

                time.sleep(polling_interval)

        raise TimeoutException(f'timeout {timeout} exceeded')

    def get_method(self, file_input):
        if not file_input:
            raise ValidationException('File input is required.')

        if not isinstance(file_input, str):
            raise ValidationException('File input must be a string (URL, path, or base64).')

        # 1. Check for URL
        try:
            # More robust URL check
            parsed_url = urlparse(file_input)
            if parsed_url.scheme in ['http', 'https'] and parsed_url.netloc:
                response = requests.get(file_input, timeout=10) # Added timeout
                response.raise_for_status() # Raises an exception for bad status codes
                return {'method': 'base64', 'body': base64.b64encode(response.content).decode('utf-8')}
        except requests.RequestException as e:
            raise ValidationException(f'Failed to download file from URL: {file_input}. Error: {e}')
        except ValueError: # Handle cases where urlparse might fail on weird strings
            pass


        # 2. Check for existing file path
        if os.path.exists(file_input):
            # It's a local file path
            return {'method': 'post', 'file': file_input}

        # 3. Check for base64 string
        if self._is_base64_like(file_input):
            return {'method': 'base64', 'body': file_input}
        
        # 4. If none of the above
        raise ValidationException(f'Invalid file input: "{file_input[:100]}...". Not a valid URL, existing file path, or base64 string.')


    def send(self, **kwargs):
        """This method can be used for manual captcha submission

        Parameters
        _________
        kwargs: dict

        Returns

        """

        params = self.default_params(kwargs)
        params = self.rename_params(params)

        params, files = self.check_hint_img(params)

        response = self.api_client.in_(files=files, **params)

        if not response.startswith('OK|'):
            raise ApiException(f'cannot recognize response {response}')

        return response[3:]

    def get_result(self, id_):
        """This method can be used for manual captcha answer polling.

        Parameters
        __________
        id_ : str
            ID of the captcha sent for solution
        Returns

        answer : text
        """

        response = self.api_client.res(key=self.api_key, action='get', id=id_)

        if response == 'CAPCHA_NOT_READY':
            raise NetworkException

        if not response.startswith('OK|'):
            raise ApiException(f'cannot recognize response {response}')

        return response[3:]

    def balance(self):
        '''Get my balance

        Returns

        balance : float
        '''

        response = self.api_client.res(key=self.api_key, action='getbalance')
        return float(response)

    def report(self, id_, correct):
        '''Report of solved captcha: good/bad.

        Parameters
        __________
        id_ : str
            captcha ID

        correct : bool
            True/False

        Returns
            None.

        '''

        rep = 'reportgood' if correct else 'reportbad'
        self.api_client.res(key=self.api_key, action=rep, id=id_)

        return

    def rename_params(self, params):

        replace = {
            'case_sensitive': 'regsense', # key changed
            'min_len': 'min_len',         # key changed (was minLen)
            'max_len': 'max_len',         # key changed (was maxLen)
            # 'minLength': 'min_len',    # This was a duplicate target, removed. min_len is preferred.
            # 'maxLength': 'max_len',    # This was a duplicate target, removed. max_len is preferred.
            'hint_text': 'textinstructions', # key changed
            'hint_img': 'imginstructions',  # key changed
            'url': 'pageurl',
            'score': 'min_score',
            'text': 'textcaptcha',
            'rows': 'recaptcharows',
            'cols': 'recaptchacols',
            'previous_id': 'previousID',    # key changed
            'can_skip': 'can_no_answer',    # key changed
            'api_server': 'api_server',     # key changed
            'soft_id': 'soft_id',         # key changed
            'callback': 'pingback',
            'datas': 'data-s',
            'site_key': 'sitekey', # For hcaptcha, turnstile etc if they pass 'site_key'
            'captcha_id': 'captchaid', # For geetest_v4, lemin
            'app_id': 'appid', # For tencent, atb_captcha
            'api_key': 'apikey', # For cutcaptcha (distinct from self.api_key for the service)
                                 # Note: 'apikey' is also a parameter name in cutcaptcha method,
                                 # so this maps the python param 'api_key_param' to API param 'apikey'
        }
        # Handle specific case for 'minLength' and 'maxLength' if they are still present
        # and different from 'min_len'/'max_len' which are now the standard.
        # However, standardizing to min_len and max_len for method parameters is better.
        # The docstrings already use minLen/maxLen, so those should be min_len/max_len.
        # If methods explicitly use minLength/maxLength, they should be changed to min_len/max_len.
        # The current replace dict uses the new snake_case keys.

        new_params = {}
        # Use a copy of params.keys() for iteration as we might pop from params
        for k in list(params.keys()):
            if k in replace:
                new_params[replace[k]] = params.pop(k)
            # Special handling for userAgent -> useragent (all lowercase for API)
            elif k == 'user_agent': # Parameter name is user_agent
                 new_params['useragent'] = params.pop(k) # API expects 'useragent'
            elif k == 'sitekey': # if 'sitekey' is passed directly (e.g. from older calls)
                 new_params['sitekey'] = params.pop(k) # keep as sitekey for API if not mapped otherwise


        proxy = params.pop('proxy', '')
        if proxy and isinstance(proxy, dict): # Ensure proxy is a dict
            new_params.update({
                'proxy': proxy.get('uri'),
                'proxytype': proxy.get('type')
            })

        new_params.update(params) # Add any remaining params

        return new_params

    def default_params(self, params):

        params.update({'key': self.api_key}) # Use self.api_key

        callback_val = params.pop('callback', self.callback)
        # Use self.soft_id (already snake_case)
        soft_id_val = params.pop('soft_id', self.soft_id) # param 'soft_id' or self.soft_id

        if callback_val: params.update({'callback': callback_val}) # API param is 'callback' or 'pingback'
                                                                    # rename_params handles 'callback' -> 'pingback'
        if soft_id_val: params.update({'soft_id': soft_id_val}) # API param is 'soft_id'
                                                               # rename_params handles 'soft_id' -> 'soft_id'

        self.has_callback = bool(callback)

        return params

    def extract_files(self, files):

        if len(files) > self.max_files:
            raise ValidationException(
                f'Too many files (max: {self.max_files})')

        not_exists = [f for f in files if not (os.path.exists(f))]

        if not_exists:
            raise ValidationException(f'File not found: {not_exists}')

        files = {f'file_{e+1}': f for e, f in enumerate(files)}
        return files

    def check_hint_img(self, params):

        hint = params.pop('imginstructions', None)
        files = params.pop('files', {})

        if not hint: # hint is the path to the image or base64 string for imginstructions
            return params, files

        # Check if hint is a URL
        try:
            parsed_url = urlparse(hint)
            if parsed_url.scheme in ['http', 'https'] and parsed_url.netloc:
                # It's a URL, download and convert to base64 for imginstructions
                response = requests.get(hint, timeout=10)
                response.raise_for_status()
                # API expects imginstructions to be base64 string or a multipart file.
                # Simplest to always convert URL-sourced imginstructions to base64 string.
                # Or, we could save it to a temp file and pass as multipart, but base64 is easier.
                # The API client's in_ method doesn't distinguish 'imginstructions' for special file handling
                # if it's passed in 'params'. If 'imginstructions' is a path, it should be in 'files'.
                # For now, if it's a URL, let's assume we should make it a base64 string in params.
                # This might need adjustment if API expects imginstructions URLs directly.
                # Based on typical 2captcha API, if it's an image, it's usually sent as content.
                params['imginstructions'] = base64.b64encode(response.content).decode('utf-8')
                return params, files # Return early as we've processed it as base64
        except requests.RequestException:
            # Not a downloadable URL or failed download, proceed to check as path/base64
            pass 
        except ValueError: # urlparse failed
            pass

        # Check if hint is an existing file path
        if os.path.exists(hint):
            # It's a local file path, should be part of 'files' for multipart upload
            files['imginstructions'] = hint # Add to files dictionary
            # params.pop('imginstructions', None) # Ensure it's not also in params as a string
            return params, files
        
        # Check if hint is a base64 string (already in params)
        if self._is_base64_like(hint):
            # It's already a base64 string in params['imginstructions'], do nothing more.
            # Ensure it remains in params. The pop earlier was just to get the value.
            params['imginstructions'] = hint 
            return params, files

        # If it's none of the above valid forms for 'hint'
        raise ValidationException(f'Invalid imginstructions value: {hint}. Must be a valid URL, existing file path, or base64 string.')

        # If files dict is empty and there was a main 'file' parameter, it might have been moved
        # This part of logic might need review based on how 'file' and 'imginstructions' are handled together
        if not files and 'file' in params: # if files is empty, but there was a main file
             files = {'file': params.pop('file')} # make it the primary file
        elif not files: # if files is empty and no main 'file' param was there
             files = {}


        files.update({'imginstructions': hint}) # hint is the file path or base64 for the instruction image

        return params, files


if __name__ == '__main__':

    key = sys.argv[1]
    sol = TwoCaptcha(key)
