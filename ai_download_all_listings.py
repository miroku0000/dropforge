from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# Set up Chrome
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

# Go to eBay login
driver.get("https://www.ebay.com/signin/")
time.sleep(30)
# Login (you should handle 2FA or store cookies)
import config
driver.find_element(By.ID, "userid").send_keys(config.EBAY_USER)
driver.find_element(By.ID, "signin-continue-btn").click()
time.sleep(30)
driver.find_element(By.ID, "pass").send_keys(config.EBAY_PASS)
driver.find_element(By.ID, "sgnBt").click()

# Wait or handle 2FA if needed
time.sleep(10)

# Navigate to the traffic page
driver.get("https://www.ebay.com/sh/ovw/performance/traffic")

# Wait for the page to load
time.sleep(10)

# Optional: apply filters or date ranges using JS or element selectors

# Click the download link
download_button = driver.find_element(
    By.XPATH, "//button[contains(text(), 'Download')]"
)
download_button.click()

# Wait for download to complete
time.sleep(15)

driver.quit()
