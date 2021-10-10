# from https://github.com/vtrouter/RotMG-Headless-Launcher/blob/main/headless_launch.py
# and https://github.com/Zeroeh/RotMG-Appspot

import requests, urllib
import base64
import wmi
import hashlib
import re
import subprocess
import os, sys
import time
import xmltodict, json
import itertools
import threading
import random
import js2py
import json

try:
    application_path = os.path.dirname(os.path.abspath(__file__))
except:
    application_path = os.path.dirname(os.path.abspath(''))

CONSTANTS_FILE_JS = fr"{application_path}\constants.js"
ACCOUNTS_FILE = fr"{application_path}\accounts.json"

_, constants = js2py.run_file(CONSTANTS_FILE_JS)

with open(ACCOUNTS_FILE, 'r') as file:
    accounts = json.load(file)
    

################ CLASS ################
class Spinner:
    def __init__(self, message, delay=0.1):
        self.spinner = itertools.cycle(['-', '/', '|', '\\'])
        self.delay = delay
        self.busy = False
        self.spinner_visible = False
        sys.stdout.write(message)

    def write_next(self):
        with self._screen_lock:
            if not self.spinner_visible:
                sys.stdout.write(next(self.spinner))
                self.spinner_visible = True
                sys.stdout.flush()

    def remove_spinner(self, cleanup=False):
        with self._screen_lock:
            if self.spinner_visible:
                sys.stdout.write('\b')
                self.spinner_visible = False
                if cleanup:
                    sys.stdout.write(' ')       # overwrite spinner with blank
                    sys.stdout.write('\r')      # move to next line
                sys.stdout.flush()

    def spinner_task(self):
        while self.busy:
            self.write_next()
            time.sleep(self.delay)
            self.remove_spinner()

    def __enter__(self):
        if sys.stdout.isatty():
            self._screen_lock = threading.Lock()
            self.busy = True
            self.thread = threading.Thread(target=self.spinner_task)
            self.thread.start()

    def __exit__(self, exception, value, tb):
        if sys.stdout.isatty():
            self.busy = False
            self.remove_spinner(cleanup=True)
        else:
            sys.stdout.write('\r')

class rotmg_account():
    def __init__(self, email, passwordord):
        self._get_device_token()
        self.email = email
        self.passwordord = passwordord   
        self.packages_dict = None
        self.name = None
        self.daily_login_calendar = None
        # the base headers and params for login
        self.exalt_base_headers = {
            'User-Agent': 'UnityPlayer/2019.4.9f1 (UnityWebRequest/1.0, libcurl/7.52.0-DEV)',
            'X-Unity-Version': '2019.4.9f1'
        }
        self.exalt_base_login_params ={ 
            'game_net': 'Unity',
            'play_platform': 'Unity',
            'game_net_user_id': '',
        }
        
    def _get_device_token(self):
        c = wmi.WMI()

        concat = ''
        for obj in c.query("SELECT * FROM Win32_BaseBoard"):
            concat += obj.SerialNumber if obj.SerialNumber else ''
        for obj in c.query("SELECT * FROM Win32_BIOS"):
            concat += obj.SerialNumber if obj.SerialNumber else ''
        for obj in c.query("SELECT * FROM Win32_OperatingSystem"):
            concat += obj.SerialNumber if obj.SerialNumber else ''

        m = hashlib.sha1()
        m.update(concat.encode())
        self.device_token = m.hexdigest()
        return
    
    def _parse_access_token(self, text):
        timestamp_regex = "<AccessTokenTimestamp>(.*)<\/AccessTokenTimestamp>"
        timestamp = re.findall(timestamp_regex, text)
        if not timestamp:
            exit(f'timestamp not found in:\n{text}')
        
        token_regex = "<AccessToken>(.*)<\/AccessToken>"
        token = re.findall(token_regex, text)
        if not token:
            exit(f'token not found in:\n{text}')
        
        # timestamp = base64.b64encode(timestamp[0].encode()).decode('utf-8')
        # token = base64.b64encode(token[0].encode()).decode('utf-8')
        timestamp = timestamp[0]
        token = token[0]
        
        self.access_token = token
        self.access_token_timestamp = timestamp
        
        self._verify_token()
        
        return token, timestamp
    
    def _verify_token(self):
        
        url = "https://www.realmofthemadgod.com/account/verifyAccessTokenClient?"
        url_params = {
            'clientToken': self.device_token,
            'accessToken' : self.access_token,
            **self.exalt_base_login_params
        }
        response = requests.get(url, params=url_params, headers=self.exalt_base_headers)
        if not "Success" in response.text:
            exit("VERIFYING TOKEN ERROR:", response.text)
    
    def login(self, max_retries = 60): 
        login_try = 0
        while True:
            login_try += 1
            
            if login_try >= max_retries:
                print(f"Max login tries after {max_retries} times")
                print(f"response.url {response.url}")
                print(f"response.text {response.text}")
                exit()
            
            url = "https://www.realmofthemadgod.com/account/verify"
            payload = {
                'guid': self.email,
                'password': self.passwordord,
                'clientToken': self.device_token,
                **self.exalt_base_login_params
            }
            # what is the best method? post or get?
            # response = requests.post(url, data=payload, headers=headers)
            response = requests.get(url, params=payload, headers=self.exalt_base_headers)
            
            # if post returns an error
            if not response.ok:
                print(f"Login post failure")
                print(f"response.url {response.url}")
                print(f"response.text {response.text}")
                exit()
            
            # if post returns internal error
            if 'Internal error, please wait' in response.text:
                
                regex_expression = "Internal error, please wait (\d*) minutes to try again"
                retry_sleep_time = re.findall(regex_expression, response.text)
                if not retry_sleep_time:
                    exit(f"Regex: '{regex_expression}' not found in '{text}'.")
                
                
                retry_sleep_time = int(retry_sleep_time[0]) +1 # add 1 minute to be sure
                retry_sleep_time_seconds = retry_sleep_time*60
                
                with Spinner(f'Waiting {retry_sleep_time_seconds} seconds to retry... {login_try}/{max_retries} tries.  ', .3):
                    time.sleep(retry_sleep_time_seconds)
                continue # restart loop
            
            break # exit loop
        
        if 'WebChangePasswordDialog.passwordError' in response.text:
            exit('WebChangePasswordDialog\nPassword Error')
            
        # login successfully
        self._parse_access_token(response.text)
        return response.text
    
    def open_game(self):
        default_rotmg_path = f'C:/Users/{os.getlogin()}/Documents/RealmOfTheMadGod/Production/'
        default_rotmg_exe = f"{default_rotmg_path}/RotMG Exalt.exe"

        encoded_email = base64.b64encode(self.email.encode()).decode('utf-8')
        data = f"data:{{platform:Deca,guid:{encoded_email},token:{base64.b64encode(self.access_token.encode()).decode('utf-8')},tokenTimestamp:{base64.b64encode(self.access_token_timestamp.encode()).decode('utf-8')},tokenExpiration:MTMwMDAwMA==,env:4}}"

        subprocess.Popen([default_rotmg_exe, data])
        return
  
    def list_chars(self):
        """
        Seens to count as daily login
        
        Get account information, but dont include
            * Gift items
            * Chest items
            * Potion stash
        """
        url = "https://www.realmofthemadgod.com/char/list"
        params = {
            'do_login': 'true',
            'accessToken': self.access_token,
            **self.exalt_base_login_params
        }
        response = requests.get(url, params=params)
        if not response.ok:
            print(response.url)
            print(response.text)
            exit()

        chars_dict = xmltodict.parse(response.text)
        return chars_dict
    
    def char_dump(self):
        """
        Get all account information, including
            * Gift items
            * Chest items
            * Potion stash
        """
        
        url = "https://www.realmofthemadgod.com/char/list"
        params = {
            'muleDump': 'true',
            'ignore' : random.randint(1111, 9999), # 4 digits random num
            '_' : random.randint(1000000000000, 9999999999999), # 13 digits random num
            'accessToken': self.access_token,
        }
        response = requests.get(url, params=params)
        if not response.ok:
            print(response.url)
            print(response.text)
            exit()
        
        chars_dict = xmltodict.parse(response.text)
        return chars_dict
    
    def list_daily_quests(self):
        
        url = "https://www.realmofthemadgod.com/dailyquest/"
        params = {
            'accessToken': self.access_token,
        }
        response = requests.get(url, params=params)
        if not response.ok:
            print(response.url)
            print(response.text)
            exit()
        
    ################ CALENDAR ################
    def fetch_daily_login_calendar(self, name_items=True):
        """
        Get all account information, including
            * Gift items
            * Chest items
            * Potion stash
        """
        
        url = "https://www.realmofthemadgod.com/dailyLogin/fetchCalendar"
        params = {
            'accessToken': self.access_token,
        }
        response = requests.get(url, params=params)
        if not response.ok:
            print(response.url)
            print(response.text)
            exit()
        
        daily_login_calendar = xmltodict.parse(response.text)
        
        # order calendar days
        ordered_list = sorted(daily_login_calendar['LoginRewards']['NonConsecutive']['Login'], key=lambda k: int(k['Days']))
        
        # insert item names
        if name_items:
            for day in ordered_list:
                item_name = get_item_infos(day['ItemId']['#text'])
                if item_name is not False:
                    item_name = item_name['name']
                else:
                    item_name = 'Unknow item'
                    
                day['ItemId']['#ItemName'] = item_name
                # print(f"Dia {day['Days'].zfill(2)} - x{day['ItemId']['@quantity']: <2} - {item_name} ")
            
        daily_login_calendar['LoginRewards']['NonConsecutive']['Login'] = ordered_list
        self.daily_login_calendar = daily_login_calendar
        return daily_login_calendar
    
    def claim_login(self):
        # not working
        url="https://realmofthemadgodhrd.appspot.com/account/claimLoginReward"
        
        data = {
        }
        params={
            'accessToken': self.access_token,
            'key':''
            
        }
        response = requests.get(url, params=params,data=data, headers=self.exalt_base_headers)
        
        print(response.url)
        print(response.text)
        return
    
    def get_daily_claim_status(self):
        
        if self.daily_login_calendar is None:
            self.fetch_daily_login_calendar()
        
        msg=''
        for day_login in self.daily_login_calendar['LoginRewards']['NonConsecutive']['Login']:
            claimed= True if day_login.get('Claimed', False) is None else False
            open_to_claim= True if day_login.get('key') else False
            
            if claimed and not open_to_claim:
                claim_status= 'Already claimed'
            elif not claimed and open_to_claim:
                claim_status= 'Ready to claim'
            elif not claimed and not open_to_claim:
                claim_status= 'Not logged yet'
            msg += f"Day: {day_login['Days'].zfill(2)} | {claim_status: <15} | {day_login['ItemId']['@quantity']: >2}x {day_login['ItemId']['#ItemName']}\n" 
            # print(f"key to claim: {day_login.get('key')}")
        return msg
    
    ################ M BOXES ################
    def get_mystery_boxes(self):
        url = "https://realmofthemadgodhrd.appspot.com/mysterybox/getBoxes"
        
        url_query = {
            'accessToken' : self.access_token,
            'version' : '1.0'
        }
                
        response = requests.get(url, params=url_query)
        
        if not response.ok:
            print(response.url)
            print(response.text)
            exit()
        
        return response.text
        
    ################ PACKAGES ################
    def get_packages(self, print_results = False):
        print(f"get_packages | starting")
        url = "https://realmofthemadgodhrd.appspot.com/package/getPackages"
        
        url_query = {
            'accessToken' : self.access_token,
            'version' : '1.0'
        }
                
        response = requests.get(url, params=url_query)
        if not response.ok:
            print(response.url)
            print(response.text)
            exit()
        
        packages_dict = xmltodict.parse(response.text)
            
        if print_results:
            msg = f"| {'ID': ^10} | {'Gold': ^10} | {'Currency': ^10} | {'Title': ^40} "
            print('-'*len(msg))
            print(msg)
            print('-'*len(msg))
            for package in packages_dict['Packages']['Package']:
                msg = f"| {package['@id']: <10} | {package['Price']['@amount']: <10} | {package['Price']['@currency']: <10} | {package['@title']: <40} |"
                print(msg)
                print('-'*len(msg))
        
        self.packages_dict = packages_dict
        
        return packages_dict

    def filter_free_packages(self):
        print(f"filter_free_packages | starting")
        free_packages = list()
        
        if self.packages_dict is None:
            self.get_packages()
        
        for package in self.packages_dict['Packages']['Package']:
            if package['Price']['@amount'] == '0':
                package_infos = {
                    'title' : package['@title'],
                    'id' : package['@id'],
                    'gold_price' : package['Price']['@amount'],
                    'currency' : package['Price']['@currency'],
                }
                free_packages.append(package_infos)
        how_many_found = len(free_packages)
        
        if how_many_found == 0:
            print('No free package found :(')
            return False
        
        print(f"Found {how_many_found} free packages")
        self.free_package_list = free_packages
        
        return free_packages
        
    def purchase_package(self, package_id, price, quantity, currency):
        url = "https://www.realmofthemadgod.com/account/purchasePackage"
        
        url_query = {
            'accessToken' : self.access_token,
            'version' : '1.0'
        }
        payload = {
            'boxId' : package_id,
            'quantity' : quantity,
            'price' : price,
            'currency' : currency,
        }
        response = requests.post(url, params=url_query, data=payload)
        
        if not response.ok:
            print(response.url)
            print(response.text)
            exit()
        
        if 'MysteryBoxError.maxPurchase' in response.text:
            return False
        elif '<Success>' in response.text:
            return True
        else:
            print(response.text)
            exit('Unknow response for package purchase!')
            
    def purchase_all_packages(self, package_list, quantity='1'):
        
        for package in package_list:
            print(f"Buying - '{package}'")
            package_bought = self.purchase_package(package_id=package['id'],
                                              price=package['gold_price'],
                                              quantity=quantity,
                                              currency=package['currency'])
            if not package_bought:
                print('Max purchase for package!')
                return False
            
        print("All packs purchased successfuly")
        return True

################ FUNCS ################

def get_item_infos(item_id):
    item_infos = dict()
    item_id = int(item_id)
    
    item = constants.items[item_id]
    if not item:
        print('unknow item, update constants with muledump-render tool')
        return False
    
    item_infos['id'] = item_id
    item_infos['name'] = item[0]
    item_infos['slot_type'] = item[1]
    item_infos['tier'] = item[2]
    item_infos['fame_bonus'] = item[5]
    item_infos['feed_power'] = item[6]
    item_infos['bag_type'] = item[7]
    item_infos['soulbound'] = item[8]
    item_infos['ut_or_st'] = item[8]
    
    return item_infos

def main():
    i = 0
    for user, password in accounts.items():
        i += 1
        print('\n\n-------------------- NEW LAP --------------------')
        print(f'Lap {i}')
        print(f"user, password = {user}")

        account = rotmg_account(user, password)
        account.login(); print(f'Logged in')
        
        # list chars count as login?
        account.list_chars(); print(f'Chars fetched')
        
        calendar=account.get_daily_claim_status()
        print(calendar)
        
        x = account.list_daily_quests()
        print(x)
        exit()
        
        # buy all free packages available
        free_packages_list = account.filter_free_packages()
        if free_packages_list:
            # if there any free package
            free_packs_bought = account.purchase_all_packages(free_packages_list)
            if not free_packs_bought:
                print('Error buying package!')
        
        exit()
        # dumps account info into ./accounts/ACCOUNT_NAME.json
        chars=account.char_dump()
        output_json_path = fr"{application_path}\accounts\{chars['Chars']['Account']['Name']}.json"
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(chars, f, ensure_ascii=False, indent=2)
            
            
if __name__ == '__main__':
    main()