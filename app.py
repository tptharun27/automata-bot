import os
import streamlit as st
import time
from playwright.sync_api import sync_playwright
from pyzbar.pyzbar import decode
from PIL import Image

# --- CLOUD SERVER SETUP ---
@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

# ==========================================
# --- CONFIGURATION ---
# ==========================================
GENERATOR_LINK = st.secrets["GENERATOR_LINK"]

# ==========================================
# --- THE BRAIN: AUTOMATION FUNCTIONS ---
# ==========================================

def capture_and_scan_qr(browser, link_to_open, screenshot_filename, status_element):
    status_element.text(f"[GETTING NEW QR] Opening generator link...")
    
    page = browser.new_page()
    page.goto(link_to_open)
    # Wait until network activity settles
    page.wait_for_load_state("networkidle", timeout=10000) 
    page.wait_for_timeout(3000) 
    
    page_text = page.locator("body").inner_text().lower()
    if "too many" in page_text or "scripts" in page_text:
        status_element.text("⚠️ Google Scripts Error on generator page.")
        page.close()
        return None

    page.screenshot(path=screenshot_filename)
    page.close()

    try:
        img = Image.open(screenshot_filename)
        decoded_objects = decode(img)
        for obj in decoded_objects:
            return obj.data.decode('utf-8')
    except Exception as e:
        status_element.text(f"Error reading image: {e}")
        
    return None

def submit_id_to_website(browser, qr_url, my_id, status_element):
    status_element.text(f"[SUBMITTING] Opening page for ID: {my_id}...")
    
    page = browser.new_page()
    try:
        page.goto(qr_url)
        # Give the page a moment to establish its connection
        page.wait_for_timeout(4000) 
        
        page_text = page.locator("body").inner_text().lower()
        if "too many" in page_text or "scripts" in page_text:
            status_element.text("⚠️ Google Scripts Error before submission.")
            page.close()
            return "error"
            
        # --- THE FIX ---
        # 1. Target the Google Apps Script iframe directly
        my_iframe = page.frame_locator("iframe").first
        
        # 2. Wait up to 10 seconds specifically for the input box inside the iframe to become visible
        input_box = my_iframe.locator("input").first
        input_box.wait_for(state="visible", timeout=10000)
        
        # 3. Fill the ID
        input_box.fill(my_id)
        
        # 4. Click the exact button text shown in your screenshot
        status_element.text(f"Clicking 'Submit Attendance' for {my_id}...")
        my_iframe.locator("text=Submit Attendance").first.click()
        # ---------------
        
        page.wait_for_timeout(4000)
        
        final_text = page.locator("body").inner_text().lower()
        if "expired" in final_text:
            status_element.text(f"❌ QR Code Expired during submission for {my_id}!")
            page.close()
            return "expired"
        elif "too many" in final_text or "scripts" in final_text:
            status_element.text("⚠️ Google Scripts Error after submission.")
            page.close()
            return "error"
        
        screenshot_name = f"secret_output_{my_id}.png"
        page.screenshot(path=screenshot_name)
        page.close()
        return "success"
        
    except Exception as e:
        status_element.text(f"❌ Failed to submit ID. Taking error screenshot...")
        page.screenshot(path="error_debug.png")
        page.close()
        return "error"

# ==========================================
# --- THE FACE: STREAMLIT DASHBOARD ---
# ==========================================

st.set_page_config(page_title="Secret ID Automator", page_icon="🤖")

st.title("🤖 Secret ID Automator")
st.write("Paste your IDs below to start the bot.")

raw_ids = st.text_area("Student IDs (Paste one per line)", height=150)

if st.button("🚀 Start Automation"):
    
    if not raw_ids:
        st.error("⚠️ Please provide at least one ID.")
    else:
        id_list = [id.strip() for id in raw_ids.split('\n') if id.strip()]
        st.info(f"Starting automation for {len(id_list)} IDs. Please wait...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        error_container = st.empty() # Placeholder for error images
        
        current_qr_url = None
        temp_qr_screenshot = "temp_qr_page.png"
        
        st.subheader("Secret Outputs")
        results_container = st.container()
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            for i, student_id in enumerate(id_list):
                success = False
                attempts = 0 # Track how many times we try this ID
                
                while not success and attempts < 3:
                    attempts += 1
                    error_container.empty() # Clear old errors
                    
                    if not current_qr_url:
                        current_qr_url = capture_and_scan_qr(browser, GENERATOR_LINK, temp_qr_screenshot, status_text)
                        if not current_qr_url:
                            status_text.text("Failed to get QR Code. Retrying in 5 seconds...")
                            time.sleep(5)
                            continue
                            
                    result = submit_id_to_website(browser, current_qr_url, student_id, status_text)
                    
                    if result == "success":
                        success = True
                        img_path = f"secret_output_{student_id}.png"
                        if os.path.exists(img_path):
                            with results_container:
                                st.image(img_path, caption=f"Output for ID: {student_id}")
                    
                    elif result == "expired":
                        current_qr_url = None 
                        
                    elif result == "error":
                        status_text.text(f"Attempt {attempts}/3 failed. Retrying in 5 seconds...")
                        # If the bot saved an error screenshot, show it on the phone!
                        if os.path.exists("error_debug.png"):
                            error_container.image("error_debug.png", caption="⚠️ What the bot saw when it crashed")
                        time.sleep(5)
                
                if not success:
                    st.error(f"Failed to process ID {student_id} after 3 attempts. Skipping to next.")
                
                progress_bar.progress((i + 1) / len(id_list))
                
        status_text.text("✅ Automation Loop Finished!")
        if os.path.exists(temp_qr_screenshot):
            os.remove(temp_qr_screenshot)
