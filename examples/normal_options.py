import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from twocaptcha import TwoCaptcha

# in this example we store the API key inside environment variables that can be set like:
# export APIKEY_2CAPTCHA=1abc234de56fab7c89012d34e56fa7b8 on Linux or macOS
# set APIKEY_2CAPTCHA=1abc234de56fab7c89012d34e56fa7b8 on Windows
# you can just set the API key directly to it's value like:
# api_key="1abc234de56fab7c89012d34e56fa7b8"

api_key = os.getenv('APIKEY_2CAPTCHA', 'YOUR_API_KEY')

solver = TwoCaptcha(api_key, default_timeout=30, polling_interval=5) # defaultTimeout -> default_timeout, pollingInterval -> polling_interval

try:
    result = solver.normal(
        file_input='./images/normal_2.jpg', # Added file_input=
        numeric=4,
        min_len=4, # minLen -> min_len
        max_len=20, # maxLen -> max_len
        phrase=0,
        case_sensitive=0, # caseSensitive -> case_sensitive
        calc=0,
        lang='en',
        # hint_img='./images/normal_hint.jpg', # hintImg -> hint_img
        # hint_text='Type red symbols only', # hintText -> hint_text
    )

except Exception as e:
    sys.exit(e)

else:
    sys.exit('result: ' + str(result))
