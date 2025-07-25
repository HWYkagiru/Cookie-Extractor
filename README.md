# Cookie-Extractor

A tool to extract cookies from browser profiles using headless automation.

## Overview

This script uses headless Selenium to access browser profiles and extract cookies, bypassing new encryption methods used by Chrome-based browsers that prevent decryption.  
It takes longer than direct decryption, but at least it works.

## Some Context

Recent changes in Chrome’s cookie encryption make it almost impossible to decrypt cookies using standard Windows APIs.  
After researching online and not finding a working "Cookie Extractor", I decided to make an alternative.  
This tool gets around the limitation by automating the browser itself to retrieve cookies directly.

## Warning

I haven't tested this tool on any browsers other than Brave. If you find any errors regarding paths or cookie extraction, feel free to open an issue.

---
