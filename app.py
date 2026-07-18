import os
import streamlit as st
import time
from playwright.sync_api import sync_playwright
from pyzbar.pyzbar import decode
from PIL import Image

# --- CLOUD SERVER SETUP ---
os.system("playwright install chromium")

# ==========================================
# --- CONFIGURATION ---
# ==========================================
GENERATOR_LINK = st.secrets["GENERATOR_LINK"]

# ==========================================
# --- THE BRAIN: AUTOMATION FUNCTIONS ---
# ==========================================

def capture_and_scan_qr(browser, link_to_open, screenshot_filename, status_element):
    status_element.text(f"[GETTING NEW QR] Opening generator link...")
    
    # Open a new tab (page) in the existing browser
    page = browser.new_page()
    page.goto(link_to_open)
    page.wait_for_timeout(3000) 
    
    page_text = page.locator("body").inner_text().lower()
    if "too many" in page_text or "scripts" in page_text:
        status_element.text("⚠️ Google Scripts Error on generator page.")
        page.close() # Close only the tab
        return None

    page.screenshot(path=screenshot_filename)
    page.close() # Close only the tab

    try:
        img = Image.open(screenshot_filename)
        decoded_objects = decode(img)
        for obj in decoded_objects:
            return obj.data.decode('utf-8')
    except Exception as e:
        status_element.text(f"Error reading image: {e}")
        
    return None

def submit_id_to_website(browser, qr_url, my_id, status_element):
    status_element.text(f"[SUBMITTING] Submitting ID: {my_id}...")
    
    # Open a new tab (page) in the existing browser
    page = browser.new_page()
    page.goto(qr_url)
    page.wait_for_timeout(4000) 
    
    page_text = page.locator("body").inner_text().lower()
    if "too many" in page_text or "scripts" in page_text:
        status_element.text("⚠️ Google Scripts Error before submission.")
        page.close()
        return "error"
        
    try:
        target_frame = page.main_frame
        for frame in page.frames:
            if frame.locator("input").count() > 0:
                target_frame = frame
                break
        
        target_frame.locator("input").first.fill(my_id)
        status_element.text(f"Clicking 'Submit' for {my_id}...")
        target_frame.locator("text=Submit").first.click()
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
        status_element.text(f"❌ Failed to find the input box. Error: {e}")
        page.close()
        return "error"

# ==========================================
# --- THE FACE: STREAMLIT DASHBOARD ---
# ==========================================

st.set_page_config(page_title="Secret ID Automator", page_icon="🤖")

st.title("🤖 Secret ID Automator")
st.write("Paste your IDs below to start the bot.")

# --- USER INPUTS ---
raw_ids = st.text_area("Student IDs (Paste one per line)", height=150)

# --- AUTOMATION TRIGGER ---
if st.button("🚀 Start Automation"):
    
    if not raw_ids:
        st.error("⚠️ Please provide at least one ID.")
    else:
        id_list = [id.strip() for id in raw_ids.split('\n') if id.strip()]
        st.info(f"Starting automation for {len(id_list)} IDs. Please wait...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        current_qr_url = None
        temp_qr_screenshot = "temp_qr_page.png"
        
        st.subheader("Secret Outputs")
        results_container = st.container()
        
        # --- BROWSER LIFECYCLE MANAGEMENT ---
        # 1. Launch the browser ONCE before the loop begins
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            # 2. Run the loop, passing the active browser to the functions
            for i, student_id in enumerate(id_list):
                success = False
                while not success:
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
                        status_text.text("Encountered a script error. Retrying same ID in 5 seconds...")
                        time.sleep(5)
                
                progress_bar.progress((i + 1) / len(id_list))
                
            # 3. The browser automatically closes here when the 'with' block finishes
            
        status_text.text("✅ All IDs Processed Successfully!")
        st.success("Automation Complete!")
        
        if os.path.exists(temp_qr_screenshot):
            os.remove(temp_qr_screenshot)
