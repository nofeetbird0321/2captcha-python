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


config = {
            'server':           '2captcha.com', # can be also set to 'rucaptcha.com'
    		'api_key':           api_key, # apiKey -> api_key
    		'soft_id':            123, # softId -> soft_id
    		# 'callback':         'https://your.site/result-receiver', # if set, sovler with just return captchaId, not polling API for the answer
    		'default_timeout':    120, # defaultTimeout -> default_timeout
    		'recaptcha_timeout':  600, # recaptchaTimeout -> recaptcha_timeout
    		'polling_interval':   10, # pollingInterval -> polling_interval
	    }

solver = TwoCaptcha(**config)

try:
    result = solver.recaptcha(
        site_key='6LfDxboZAAAAAD6GHukjvUy6lszoeG3H4nQW57b6', # sitekey -> site_key
        url='https://2captcha.com/demo/recaptcha-v2-invisible?level=low',
        invisible=1,
        enterprise=0
#        proxy={
#            'type': 'HTTPS',
#            'uri': 'login:password@IP_address:PORT'
#        }
        )

except Exception as e:
    sys.exit(e)

else:
    sys.exit('result: ' + str(result))
