import os
try:
    import requests
except:
    print("没有找到requests,尝试下载--")
    os.system(f'pip install requests')
    import requests
import zipfile
import json
 
root = "."
 
 
def removeDirs(path, dir):
    if os.path.exists(os.path.join(path, dir)):
        path = os.path.join(path, dir)
        if os.path.isdir(path):
            os.chdir(path)
            absPath = os.getcwd()
            for inner in os.listdir('.'):
                if os.path.isdir(inner):
                    removeDirs(os.getcwd(), inner)
                    continue
                os.remove(inner)
            os.chdir(absPath[:absPath.rfind("\\")])
            os.removedirs(dir)
        else:
            os.remove(path)
 
 
def update_driver():
    url = 'https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json'
    resp = json.loads(requests.get(url).text)
    for platforms in resp['channels']['Stable']['downloads']['chromedriver']:
        if platforms['platform'] == "win64":
            zips = platforms['url']
            file = requests.get(zips).content
            with open('./chromedriver-win64.zip', 'wb') as f:
                f.write(file)
            zip_file = zipfile.ZipFile('chromedriver-win64.zip')
            name_ = filter(lambda x: x.endswith(".exe"), zip_file.namelist()).__next__()
            zip_file.extract(name_, root)
            if os.path.exists(f'{root}\chromedriver.exe'):
                os.remove(f'{root}\chromedriver.exe')
            zip_file.close()
            os.rename(os.path.join(root, name_), f'{root}\chromedriver.exe')
            removeDirs(root, 'chromedriver-win64')
            removeDirs(root, 'chromedriver-win64.zip')
 
 
update_driver()