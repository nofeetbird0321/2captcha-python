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

solver = TwoCaptcha(api_key, default_timeout=120, polling_interval=5, server='2captcha.com') # defaultTimeout -> default_timeout, pollingInterval -> polling_interval

try:
    result = solver.canvas(
        file_input='./images/canvas.jpg', # Added file_input=
        previous_id=0, # previousId -> previous_id
        can_skip=0, # canSkip -> can_skip
        lang='en',
        hint_img='./images/canvas_hint.jpg', # hintImg -> hint_img
        hint_text='Draw around apple', # hintText -> hint_text
    )

except Exception as e:  
    sys.exit(e)

else:
    sys.exit('result: ' + str(result))
